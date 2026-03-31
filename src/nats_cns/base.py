"""
Central Nervous System (NATS).

Author: Dimitris Gkoulis
Created on: Saturday 28 October 2023
Modified on: Tuesday 31 March 2026
"""

import asyncio
import inspect
import logging
import os
import pickle
import queue
import re
import signal
import threading
import time
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Event
from typing import Any, Callable, Dict, List, Optional

import nats.errors
from nats.aio.client import Client as NATSClient, Msg, Subscription

_logger = logging.getLogger("nats_cns.base")


# ####################################################################################################
# Helpers
# ####################################################################################################


def is_valid_key_portion(portion: str) -> bool:
    return bool(re.match("^[a-zA-Z][a-zA-Z0-9]*$", portion))


# ####################################################################################################
# Data Types
# ####################################################################################################


@dataclass
class EventTypeKey:
    """
    Represents a key that identifies an event type.

    ...

    Attributes
    ----------

    space : str
        The broadest categorization.
    super_family : str
        A collection of related functionality or sub-systems within the broader space.
    family : str
        Further breaking down of related functionality or sub-systems offering a more granular classification.
    name : str
        A specific function or entity within the family.
    qualifiers : list of strings
        A list with additional descriptors indicating variations, versions, or specific attributes related to the name.
        By default, it is `["root"]`.
    """

    space: str
    super_family: str
    family: str
    name: str
    qualifiers: List[str] = field(default_factory=lambda: ["root"])
    group_key: str = field(init=False)
    base_key: str = field(init=False)
    qualifiers_key: str = field(init=False)
    full_key: str = field(init=False)

    def __str__(self) -> str:
        return self.full_key

    def __post_init__(self) -> None:
        if len(self.qualifiers) == 0:
            self.qualifiers = ["root"]
        self.group_key = f"{self.space}.{self.super_family}.{self.family}"
        self.base_key = f"{self.group_key}.{self.name}"
        self.qualifiers_key = ".".join(self.qualifiers)
        self.full_key = f"{self.base_key}.{self.qualifiers_key}"

    def reuse(self, qualifiers: List[str]) -> None:
        self.qualifiers = qualifiers
        self.__post_init__()

    def validate(self) -> None:
        portions: List[str] = self.full_key.split(".")
        assert len(portions) >= 5, "portions length must be grater than or equal to 5!"
        for portion in portions:
            assert is_valid_key_portion(portion=portion) is True, f"portion {portion} is not valid!"

    def is_group(self) -> bool:
        return self.name == "root" and len(self.qualifiers) == 1 and self.qualifiers[0] == "root"

    def is_base(self) -> bool:
        return self.name != "root" and len(self.qualifiers) == 1 and self.qualifiers[0] == "root"


def parse_event_type_key(key: str) -> EventTypeKey:
    parts = key.split(".")
    assert len(parts) >= 5
    return EventTypeKey(
        space=parts[0],
        super_family=parts[1],
        family=parts[2],
        name=parts[3],
        qualifiers=parts[4:],
    )


def subject_tokens_matches_tokens(pattern_tokens: List[str], subject_tokens: List[str]) -> bool:
    if "*" in subject_tokens:
        return False

    if ">" in subject_tokens:
        return False

    if not pattern_tokens:
        return not subject_tokens

    if pattern_tokens[-1] == ">":
        # If pattern ends with '>', it matches everything afterward.
        return pattern_tokens[:-1] == subject_tokens[: len(pattern_tokens) - 1]

    if len(pattern_tokens) != len(subject_tokens):
        return False

    for p, s in zip(pattern_tokens, subject_tokens):
        if p != "*" and p != s:
            return False

    return True


def subject_matches(pattern: str, subject: str) -> bool:
    pattern_tokens = pattern.split(".")
    subject_tokens = subject.split(".")
    return subject_tokens_matches_tokens(pattern_tokens=pattern_tokens, subject_tokens=subject_tokens)


@dataclass
class EventTypeSerDe:
    etk: EventTypeKey
    serializer: Optional[Callable]
    deserializer: Optional[Callable]
    validator: Optional[Callable]

    def __post_init__(self) -> None:
        assert self.etk.is_base() is True, f"{self.etk} must represent a base key!"


@dataclass
class Event:
    key: EventTypeKey
    data: Any = field(default=None)
    metadata: Dict[str, str] = field(default_factory=lambda: {})

    def __str__(self) -> str:
        return f"Event with key : {self.key.full_key}"


# ####################################################################################################
# Communication Patterns
# ####################################################################################################


class PubSubContext:
    """
    PUB/SUB (local) context.

    ...

    Notes
    -----

    1. Only one event can be processed at a time.
    2. The implementation is not thread safe.
    """

    def __init__(self) -> None:
        self._subscriptions_map: Dict[str, Optional[Callable]] = {}
        self.publish_queue: queue.Queue = queue.Queue()
        self.subscribe_queue: queue.Queue = queue.Queue()

    # --------------------------------------------------
    # Pub/Sub: Publisher

    def publish(self, event: Event) -> None:
        """
        Not an actual publish. This method adds the event to the queue for publishing as soon as possible.
        """
        self.publish_queue.put(item=event)

    # --------------------------------------------------
    # Pub/Sub: Subscriber

    def subscribe(self, pattern: str, handler: Optional[Callable]) -> None:
        assert pattern not in self._subscriptions_map
        self._subscriptions_map[pattern] = handler

    # --------------------------------------------------
    # Entrypoints.

    def on_new_event(self, event: Event) -> None:
        matches: int = 0
        queued: bool = False

        for pattern, handler in self._subscriptions_map.items():
            # if "*" not in pattern and ">" not in pattern  # @future Optimization: compare if string has no *, >.

            if subject_matches(pattern=pattern, subject=event.key.full_key) is False:
                continue

            if handler is None:
                # We add to queue only once.
                if queued is False:
                    self.subscribe_queue.put(item=event)
                    queued = True
            else:
                try:
                    handler(event)
                except Exception as ex:
                    _logger.error(
                        f"Could not process {event}: subscription {pattern} handler failed!",
                        exc_info=ex,
                    )

            matches = matches + 1

        if matches == 0:
            _logger.warning(f"{event} did not match any pattern. Discarding!")


# ####################################################################################################
# NATS
# ####################################################################################################


async def _no_ops_nats_callback(*args, **kwargs) -> None: ...


class NATSAsyncAdapter:
    def __init__(
        self,
        servers: List[str],
        name: Optional[str],
        default_timeout: float,
    ) -> None:
        self._servers: List[str] = servers
        self._name: Optional[str] = name
        self._pid: int = os.getpid()
        self._uuid: uuid.UUID = uuid.uuid4()
        self._default_timeout: float = default_timeout
        self._nc: NATSClient = NATSClient()
        self._subscriptions: Dict[str, Subscription] = {}

    # --------------------------------------------------
    # Control

    async def start(self) -> None:
        await self._nc.connect(
            servers=self._servers,
            error_cb=_no_ops_nats_callback,
            disconnected_cb=_no_ops_nats_callback,
            closed_cb=_no_ops_nats_callback,
            discovered_server_cb=_no_ops_nats_callback,
            reconnected_cb=_no_ops_nats_callback,
            name=self._name,
        )

    async def graceful_stop(self):
        subjects: List[str] = list(self._subscriptions.keys())
        for subject in subjects:
            await self.unsubscribe(subject=subject)
        self._subscriptions = {}
        await self._nc.close()

    def get_status(self) -> int:
        # noinspection PyProtectedMember
        return self._nc._status

    # --------------------------------------------------
    # API

    async def subscribe(self, subject: str, cb: Optional[Callable]) -> None:
        assert subject not in self._subscriptions
        subscription: Subscription = await self._nc.subscribe(subject=subject, cb=cb)
        self._subscriptions[subject] = subscription

    async def subscribe_replier(self, subject: str, cb: Optional[Callable]) -> None:
        async def _replier_cb_wrapper(msg: Msg) -> None:
            response = await cb(msg=msg)
            await msg.respond(data=response)

        await self.subscribe(subject=subject, cb=_replier_cb_wrapper)

    async def unsubscribe(self, subject: str) -> None:
        assert subject in self._subscriptions
        subscription: Subscription = self._subscriptions[subject]

        try:
            await subscription.drain()
        except (
            nats.errors.ConnectionClosedError,
            nats.errors.ConnectionDrainingError,
            nats.errors.BadSubscriptionError,
        ):
            _logger.warning(f"Could not drain subscription to subject {subject}. It is probably already closed.")

        try:
            await subscription.unsubscribe()
        except (
            nats.errors.ConnectionClosedError,
            nats.errors.ConnectionDrainingError,
            nats.errors.BadSubscriptionError,
        ):
            _logger.warning(f"Could not unsubscribe from subject {subject}. It is probably already closed.")

        del self._subscriptions[subject]

    async def publish(self, subject: str, payload: bytes, headers: Optional[Dict[str, Any]]) -> None:
        await self._nc.publish(subject=subject, payload=payload, headers=headers)

    async def request(
        self,
        subject: str,
        payload: bytes,
        timeout: Optional[float],
        headers: Optional[Dict[str, Any]],
    ) -> Msg:
        if timeout is None:
            timeout = self._default_timeout
        message: Msg = await self._nc.request(subject=subject, payload=payload, timeout=timeout, headers=headers)
        return message


@dataclass
class _NATSEvent:
    subject: str
    payload: bytes
    headers: Dict[str, str]

    def __post_init__(self) -> None:
        assert "*" not in self.subject
        assert ">" not in self.subject


def _warn_could_not_process_in_msg(msg: Msg, message: str, exc_info=None):
    msg_str: str = f"Msg<{msg.subject}>"
    _logger.warning(f"Could not process incoming {msg_str}: {message}", exc_info=exc_info)


class NATSAsyncContext:
    def __init__(self, servers: List[str], name: Optional[str], default_timeout: float) -> None:
        self._nats: NATSAsyncAdapter = NATSAsyncAdapter(servers=servers, name=name, default_timeout=default_timeout)
        self._et_serde_map: Dict[str, EventTypeSerDe] = {}
        self.queue: asyncio.Queue = asyncio.Queue()

    # --------------------------------------------------
    # Control

    async def start(self) -> None:
        await self._nats.start()

    async def graceful_stop(self) -> None:
        await self._nats.graceful_stop()

    def status(self) -> int:
        return self._nats.get_status()

    # --------------------------------------------------
    # SerDe

    async def register_event_type(self, et_serde: EventTypeSerDe) -> None:
        assert et_serde.etk.is_base() is True
        assert et_serde.etk.base_key not in self._et_serde_map

        if et_serde.serializer is not None:
            assert inspect.iscoroutinefunction(et_serde.serializer) is False

        if et_serde.deserializer is not None:
            assert inspect.iscoroutinefunction(et_serde.deserializer) is False

        if et_serde.validator is not None:
            assert inspect.iscoroutinefunction(et_serde.validator) is False

        self._et_serde_map[et_serde.etk.base_key] = et_serde

    # --------------------------------------------------
    # Private

    async def _outgoing(self, event: Event) -> Optional[_NATSEvent]:
        assert event is not None, "event must not be None!"

        base_key: str = event.key.base_key
        assert base_key in self._et_serde_map, f"There is not a registered {EventTypeSerDe.__name__} for {base_key}!"

        valid: bool = True
        if self._et_serde_map[base_key].validator is not None:
            try:
                valid = self._et_serde_map[base_key].validator(event.data)
            except Exception as ex:
                _logger.error(f"Validation of {event} failed!", exc_info=ex)
                return None

        if valid is False:
            _logger.warning(f"{event} is not valid!")
            return None

        subject: str = event.key.full_key

        if self._et_serde_map[base_key].serializer is None:
            # _logger.warning(
            #     f"There is no registered {EventTypeSerDe.__name__} for {base_key}. Using `pickle` instead."
            # )
            try:
                payload: bytes = pickle.dumps(event.data)
            except Exception as ex:
                _logger.error(
                    f"Serialization (default) of {event} failed!",
                    exc_info=ex,
                )
                return None
        else:
            try:
                payload: bytes = self._et_serde_map[base_key].serializer(event.data)
            except Exception as ex:
                _logger.error(f"Serialization of {event} failed!", exc_info=ex)
                return None

        headers: Dict[str, str] = event.metadata
        headers["CNS.event_type_name_group_key"] = event.key.group_key
        headers["CNS.event_type_name_base_key"] = event.key.base_key
        headers["CNS.event_type_name_qualifiers_key"] = event.key.qualifiers_key
        headers["CNS.event_type_name_full_key"] = event.key.full_key
        headers["CNS.event_type_name_name"] = event.key.name
        headers["CNS.out_time_ns"] = str(time.time_ns())
        headers["CNS.communication_pattern"] = "pub/sub"
        # noinspection PyProtectedMember
        headers["CNS.client_name"] = self._nats._nc.options["name"]
        # noinspection PyProtectedMember
        headers["CNS.client_pid"] = str(self._nats._pid)
        # noinspection PyProtectedMember
        headers["CNS.client_uuid"] = self._nats._uuid.__str__()

        return _NATSEvent(
            subject=subject,
            payload=payload,
            headers=headers,
        )

    async def _incoming(self, message: Msg) -> Optional[Event]:
        assert message is not None

        if message.headers is None:
            _warn_could_not_process_in_msg(msg=message, message="headers dict is None")
            return None

        headers: Dict[str, str] = message.headers

        if "CNS.event_type_name_full_key" not in headers:
            _warn_could_not_process_in_msg(
                msg=message,
                message="headers dict does not contain the `CNS.event_type_name_full_key` header",
            )
            return None

        etn_full_key: str = headers["CNS.event_type_name_full_key"]

        try:
            key: EventTypeKey = parse_event_type_key(key=etn_full_key)
        except Exception as ex:
            _warn_could_not_process_in_msg(
                msg=message,
                message=f"{etn_full_key} could not be parsed to {EventTypeKey.__name__}",
                exc_info=ex,
            )
            return None

        etn_base_key: str = key.base_key

        if etn_base_key not in self._et_serde_map:
            _warn_could_not_process_in_msg(
                msg=message,
                message=f"there is not a registered {EventTypeSerDe.__name__} for {etn_base_key}",
            )
            return None

        if self._et_serde_map[etn_base_key].deserializer is None:
            try:
                data = pickle.loads(message.data)
            except Exception as ex:
                _warn_could_not_process_in_msg(
                    msg=message,
                    message=f"deserialization (default) failed",
                    exc_info=ex,
                )
                return None
        else:
            try:
                data = self._et_serde_map[etn_base_key].deserializer(message.data)
            except Exception as ex:
                _warn_could_not_process_in_msg(msg=message, message=f"deserialization failed", exc_info=ex)
                return None

        valid: bool = True
        if self._et_serde_map[etn_base_key].validator is not None:
            valid = self._et_serde_map[etn_base_key].validator(data)

        if valid is False:
            _warn_could_not_process_in_msg(msg=message, message=f"validation failed")
            return None

        metadata: Dict[str, str] = headers
        metadata["CNS.in_time_ns"] = str(time.time_ns())

        return Event(key=key, data=data, metadata=metadata)

    async def _incoming_subscription(self, message: Msg) -> None:
        event: Optional[Event] = await self._incoming(message=message)
        if event is None:
            return
        await self.queue.put(item=event)

    # --------------------------------------------------
    # Pub/Sub

    async def publish(self, event: Event) -> None:
        nats_event: Optional[_NATSEvent] = await self._outgoing(event=event)
        if nats_event is None:
            return
        await self._nats.publish(
            subject=nats_event.subject,
            payload=nats_event.payload,
            headers=nats_event.headers,
        )

    async def subscribe(self, subject: str) -> None:
        _logger.info(f"Subscribing to subject : {subject}")
        await self._nats.subscribe(subject=subject, cb=self._incoming_subscription)

    async def unsubscribe(self, subject: str) -> None:
        _logger.info(f"Unsubscribe to subject : {subject}")
        await self._nats.unsubscribe(subject=subject)


# ####################################################################################################
# Opinionated Usage: PSLC
# ####################################################################################################


class IPrivateSharedLocalContext(ABC):
    """
    Private Shared Local Context (PSLC) Interface.
    """

    def __init__(self) -> None:
        self.active_state: bool = True
        self.nc_a_ctx: NATSAsyncContext | None = None
        self.ps_ctx: PubSubContext | None = None
        self.thread1: threading.Thread | None = None
        self.thread_pool_executor1: ThreadPoolExecutor | None = None
        self._loop = None

    # noinspection PyAttributeOutsideInit
    def set_parameters(
        self,
        servers: List[str],
        name: Optional[str],
        default_timeout: float,
        queue_ops_timeout: float,
        enable_pub: bool,
        enable_sub: bool,
        max_workers: int,
    ) -> None:
        # Can be called only once!
        self._servers: List[str] = servers
        self._name: str = name
        self._default_timeout: float = default_timeout
        self._queue_ops_timeout: float = queue_ops_timeout
        self._enable_pub: bool = enable_pub
        self._enable_sub: bool = enable_sub
        self._max_workers: int = max_workers

        if self._enable_pub is True and self._enable_sub is True and self._max_workers <= 1:
            _logger.warning(
                f"Both pub and sub are enabled but max_workers ({self._max_workers}) is less than 1. "
                "That will add significant latency to event processing!"
            )

        if (
            (self._enable_pub is True and self._enable_sub is False)
            or (self._enable_pub is False and self._enable_sub is True)
            and self._max_workers > 1
        ):
            _logger.warning(
                f"Not both pub or sub are enabled but max_workers ({self._max_workers}) is greater than 1. "
                "It is highly recommended to set `max_workers=1`"
            )

    async def asynchronous_setup(self) -> None:
        self.nc_a_ctx = NATSAsyncContext(
            servers=self._servers,
            name=self._name,
            default_timeout=self._default_timeout,
        )
        await self.nc_a_ctx.start()
        await self._asynchronous_setup__post()

    def synchronous_setup(self) -> None:
        self.ps_ctx = PubSubContext()
        self._synchronous_setup__post()

    @abstractmethod
    async def _asynchronous_setup__post(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _synchronous_setup__post(self) -> None:
        raise NotImplementedError

    # --------------------------------------------------
    # Context Transfers

    async def transfer_events_from_async_subscribe_to_sync_subscribe(self) -> None:
        _logger.debug("Starting `transfer_events_from_async_subscribe_to_sync_subscribe`")
        timeout: float = self._queue_ops_timeout
        # @future Use (asyncio) event instead of `active_state` ?
        while self.active_state is True:
            try:
                event: Event = await asyncio.wait_for(self.nc_a_ctx.queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                continue

            self.nc_a_ctx.queue.task_done()  # dequeue is our task.

            # DO NOT CALL DIRECTLY! THIS MAY BLOCK THE LOOP.
            # self.ps_ctx.on_new_event(event=event)

            # IMPORTANT: `on_new_event` may call multiple callbacks.
            # Avoid using callbacks. Just add events to the corresponding queue and consume them later.
            # However, if callbacks cannot be avoided, prefer lightweight functions
            # that do no perform CPU intensive operations.
            await asyncio.get_event_loop().run_in_executor(self.thread_pool_executor1, self.ps_ctx.on_new_event, event)

        _logger.debug("`transfer_events_from_async_subscribe_to_sync_subscribe` exited infinite loop")

    async def transfer_events_from_sync_publish_to_async_publish(self) -> None:
        _logger.debug("Starting `transfer_events_from_sync_publish_to_async_publish`")
        timeout: float = self._queue_ops_timeout
        # @future Use (asyncio) event instead of `active_state` ?
        while self.active_state is True:
            try:
                # DO NOT CALL DIRECTLY! THIS MAY BLOCK THE LOOP.
                # event: Event = self.ps_ctx.publish_queue.get(block=True, timeout=1.0)

                event: Event = await asyncio.get_event_loop().run_in_executor(
                    self.thread_pool_executor1,
                    self.ps_ctx.publish_queue.get,
                    True,
                    timeout,
                )
            except queue.Empty:
                continue
            except RuntimeError as ex:
                ex_str: str = str(ex)
                if ex_str == "cannot schedule new futures after shutdown":
                    # @future Find a way to not reach this block. Synchronous graceful shutdown.
                    _logger.warning(ex_str)
                    break
                raise ex
            await self.nc_a_ctx.publish(event=event)

        _logger.debug("`transfer_events_from_sync_publish_to_async_publish` exited infinite loop")

    async def infinite_transferring(self) -> None:
        tasks = []

        if self._enable_pub is True:
            tasks.append(self.transfer_events_from_sync_publish_to_async_publish())

        if self._enable_sub is True:
            tasks.append(self.transfer_events_from_async_subscribe_to_sync_subscribe())

        assert len(tasks) > 0
        assert asyncio.get_running_loop() is self._loop
        await asyncio.gather(*tasks)

    def asynchronous_context_runnable(self, debug: bool = False) -> None:
        self._loop = asyncio.new_event_loop()
        self._loop.set_debug(enabled=debug)
        asyncio.set_event_loop(loop=self._loop)
        self._loop.run_until_complete(self.asynchronous_setup())
        self._loop.run_until_complete(self.infinite_transferring())  # Blocks.
        self._loop.run_until_complete(self.nc_a_ctx.graceful_stop())
        self._loop.stop()

    # --------------------------------------------------
    # Helpers

    def invoke_asynchronous_context_runnable(self) -> None:
        self.thread_pool_executor1 = ThreadPoolExecutor(max_workers=self._max_workers, thread_name_prefix="CNSACRWorker")
        self.thread1 = threading.Thread(target=self.asynchronous_context_runnable, name="CNSACRThread")
        self.thread1.start()

    def set_signals_handlers(self) -> None:
        assert threading.current_thread() == threading.main_thread()

        has_current_handler = False
        current_handler = signal.getsignal(signal.SIGINT)

        if current_handler == signal.SIG_DFL:
            pass
        elif current_handler == signal.SIG_IGN:
            pass
        else:
            has_current_handler = True

        # noinspection PyUnusedLocal
        def _signal_handler_func(signum, frame) -> None:
            self.active_state = False
            if has_current_handler is True:
                current_handler(signum, frame)

        signal.signal(signal.SIGINT, _signal_handler_func)
        # signal.signal(signal.SIGTERM, _signal_handler_func)

    # --------------------------------------------------
    # Convenient helpers for polling

    def get_all_until_now(self, max_size: int) -> List[Event]:
        counter: int = 0
        events: List[Event] = []

        while True:
            if 0 < max_size <= counter:
                break

            try:
                event: Event = self.ps_ctx.subscribe_queue.get_nowait()
            except queue.Empty:
                break

            events.append(event)
            counter = counter + 1

        return events

    def get_all_until_now_or_block_with_timeout(self, max_size: int, timeout: float) -> List[Event]:
        events: List[Event] = self.get_all_until_now(max_size=max_size)

        if len(events) > 0:
            return events

        try:
            event: Event = self.ps_ctx.subscribe_queue.get(block=True, timeout=timeout)
            return [event]
        except queue.Empty:
            return []


# ####################################################################################################
# Polling helpers.
# ####################################################################################################


def organize_events_by_group_key(events: List[Event]) -> Dict[str, List[Event]]:
    organized: Dict[str, List[Event]] = {}
    for event in events:
        key_str: str = event.key.group_key
        if key_str not in organized:
            organized[key_str] = []
        organized[key_str].append(event)
    return organized


def organize_events_by_base_key(events: List[Event]) -> Dict[str, List[Event]]:
    organized: Dict[str, List[Event]] = {}
    for event in events:
        key_str: str = event.key.base_key
        if key_str not in organized:
            organized[key_str] = []
        organized[key_str].append(event)
    return organized


def organize_events_by_full_key(events: List[Event]) -> Dict[str, List[Event]]:
    organized: Dict[str, List[Event]] = {}
    for event in events:
        key_str: str = event.key.full_key
        if key_str not in organized:
            organized[key_str] = []
        organized[key_str].append(event)
    return organized


# ####################################################################################################
# Lightweight Event Definition.
# ####################################################################################################


class LightweightEventDefinition:
    def __init__(
        self,
        key_str: str,
        serializer: Optional[Callable],
        deserializer: Optional[Callable],
        validator: Optional[Callable],
    ) -> None:
        self.key: EventTypeKey = parse_event_type_key(key=key_str)
        assert self.key.is_base() is True
        self.serde: EventTypeSerDe = EventTypeSerDe(
            etk=self.key,
            serializer=serializer,
            deserializer=deserializer,
            validator=validator,
        )

    def new_key(self, qualifier: str) -> EventTypeKey:
        return EventTypeKey(
            space=self.key.space,
            super_family=self.key.super_family,
            family=self.key.family,
            name=self.key.name,
            qualifiers=[qualifier],
        )

    def new_key2(self, qualifiers: List[str]) -> EventTypeKey:
        return EventTypeKey(
            space=self.key.space,
            super_family=self.key.super_family,
            family=self.key.family,
            name=self.key.name,
            qualifiers=qualifiers,
        )


class LightweightEventDefinitionsGroup:
    def __init__(self, group_key_str: str) -> None:
        self._etk: EventTypeKey = parse_event_type_key(key=group_key_str)
        assert self._etk.is_group() is True
        self._map: Dict[str, LightweightEventDefinition] = {}

    def register(self, definition: LightweightEventDefinition) -> None:
        assert definition.key.is_base() is True
        assert definition.key.group_key == self._etk.group_key
        assert definition.key.name not in self._map, f"{definition.key.name} is already registered in {self._etk.group_key} group"
        self._map[definition.key.name] = definition

    def unregister(self, name: str) -> None:
        assert name in self._map, f"{name} is not registered in {self._etk.group_key} group"
        del self._map[name]

    def get_by_name(self, name: str) -> LightweightEventDefinition:
        assert name in self._map, f"{name} is not registered in {self._etk.group_key} group"
        return self._map[name]


def simple_type_validator_factory(expected_type) -> Callable:
    def _type_validation_func(obj: Any) -> bool:
        return type(obj) == expected_type

    return _type_validation_func
