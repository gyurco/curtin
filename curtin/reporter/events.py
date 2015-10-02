#   Copyright (C) 2015 Canonical Ltd.
#
#   Author: Scott Moser <scott.moser@canonical.com>
#
#   Curtin is free software: you can redistribute it and/or modify it under
#   the terms of the GNU Affero General Public License as published by the
#   Free Software Foundation, either version 3 of the License, or (at your
#   option) any later version.
#
#   Curtin is distributed in the hope that it will be useful, but WITHOUT ANY
#   WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
#   FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for
#   more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with Curtin.  If not, see <http://www.gnu.org/licenses/>.
"""
cloud-init reporting framework

The reporting framework is intended to allow all parts of cloud-init to
report events in a structured manner.
"""
import base64
import os.path
import time

from . import instantiated_handler_registry

FINISH_EVENT_TYPE = 'finish'
START_EVENT_TYPE = 'start'
RESULT_EVENT_TYPE = 'result'

DEFAULT_EVENT_ORIGIN = 'curtin'


class _nameset(set):
    def __getattr__(self, name):
        if name in self:
            return name
        raise AttributeError("%s not a valid value" % name)


status = _nameset(("SUCCESS", "WARN", "FAIL"))


class ReportingEvent(object):
    """Encapsulation of event formatting."""

    def __init__(self, event_type, name, description,
                 origin=DEFAULT_EVENT_ORIGIN, timestamp=time.time()):
        self.event_type = event_type
        self.name = name
        self.description = description
        self.origin = origin
        self.timestamp = timestamp

    def as_string(self):
        """The event represented as a string."""
        return '{0}: {1}: {2}'.format(
            self.event_type, self.name, self.description)

    def as_dict(self):
        """The event represented as a dictionary."""
        return {'name': self.name, 'description': self.description,
                'event_type': self.event_type, 'origin': self.origin,
                'timestamp': self.timestamp}


class FinishReportingEvent(ReportingEvent):

    def __init__(self, name, description, result=status.SUCCESS,
                 post_files=None):
        super(FinishReportingEvent, self).__init__(
            FINISH_EVENT_TYPE, name, description)
        self.result = result
        if post_files is None:
            post_files = []
        self.post_files = post_files
        if result not in status:
            raise ValueError("Invalid result: %s" % result)

    def as_string(self):
        return '{0}: {1}: {2}: {3}'.format(
            self.event_type, self.name, self.result, self.description)

    def as_dict(self):
        """The event represented as json friendly."""
        data = super(FinishReportingEvent, self).as_dict()
        data['result'] = self.result
        if self.post_files:
            data['files'] = _collect_file_info(self.post_files)
        return data


def report_event(event):
    """Report an event to all registered event handlers.

    This should generally be called via one of the other functions in
    the reporting module.

    :param event_type:
        The type of the event; this should be a constant from the
        reporting module.
    """
    for _, handler in instantiated_handler_registry.registered_items.items():
        handler.publish_event(event)


def report_finish_event(event_name, event_description,
                        result=status.SUCCESS, post_files=None):
    """Report a "finish" event.

    See :py:func:`.report_event` for parameter details.
    """
    event = FinishReportingEvent(event_name, event_description, result,
                                 post_files=post_files)
    return report_event(event)


def report_start_event(event_name, event_description):
    """Report a "start" event.

    :param event_name:
        The name of the event; this should be a topic which events would
        share (e.g. it will be the same for start and finish events).

    :param event_description:
        A human-readable description of the event that has occurred.
    """
    event = ReportingEvent(START_EVENT_TYPE, event_name, event_description)
    return report_event(event)


class ReportEventStack(object):
    """Context Manager for using :py:func:`report_event`

    This enables calling :py:func:`report_start_event` and
    :py:func:`report_finish_event` through a context manager.

    :param name:
        the name of the event

    :param description:
        the event's description, passed on to :py:func:`report_start_event`

    :param message:
        the description to use for the finish event. defaults to
        :param:description.

    :param parent:
    :type parent: :py:class:ReportEventStack or None
        The parent of this event.  The parent is populated with
        results of all its children.  The name used in reporting
        is <parent.name>/<name>

    :param reporting_enabled:
        Indicates if reporting events should be generated.
        If not provided, defaults to the parent's value, or True if no parent
        is provided.

    :param result_on_exception:
        The result value to set if an exception is caught. default
        value is FAIL.
    """
    def __init__(self, name, description, message=None, parent=None,
                 reporting_enabled=None, result_on_exception=status.FAIL,
                 post_files=None):
        self.parent = parent
        self.name = name
        self.description = description
        self.message = message
        self.result_on_exception = result_on_exception
        self.result = status.SUCCESS
        if post_files is None:
            post_files = []
        self.post_files = post_files

        # use parents reporting value if not provided
        if reporting_enabled is None:
            if parent:
                reporting_enabled = parent.reporting_enabled
            else:
                reporting_enabled = True
        self.reporting_enabled = reporting_enabled

        if parent:
            self.fullname = '/'.join((parent.fullname, name,))
        else:
            self.fullname = self.name
        self.children = {}

    def __repr__(self):
        return ("ReportEventStack(%s, %s, reporting_enabled=%s)" %
                (self.name, self.description, self.reporting_enabled))

    def __enter__(self):
        self.result = status.SUCCESS
        if self.reporting_enabled:
            report_start_event(self.fullname, self.description)
        if self.parent:
            self.parent.children[self.name] = (None, None)
        return self

    def _childrens_finish_info(self):
        for cand_result in (status.FAIL, status.WARN):
            for name, (value, msg) in self.children.items():
                if value == cand_result:
                    return (value, self.message)
        return (self.result, self.message)

    @property
    def result(self):
        return self._result

    @result.setter
    def result(self, value):
        if value not in status:
            raise ValueError("'%s' not a valid result" % value)
        self._result = value

    @property
    def message(self):
        if self._message is not None:
            return self._message
        return self.description

    @message.setter
    def message(self, value):
        self._message = value

    def _finish_info(self, exc):
        # return tuple of description, and value
        # explicitly handle sys.exit(0) as not an error
        if exc and not(isinstance(exc, SystemExit) and exc.code == 0):
            return (self.result_on_exception, self.message)
        return self._childrens_finish_info()

    def __exit__(self, exc_type, exc_value, traceback):
        (result, msg) = self._finish_info(exc_value)
        if self.parent:
            self.parent.children[self.name] = (result, msg)
        if self.reporting_enabled:
            report_finish_event(self.fullname, msg, result,
                                post_files=self.post_files)


def _collect_file_info(files):
    if not files:
        return None
    ret = []
    for fname in files:
        if not os.path.isfile(fname):
            content = None
        else:
            with open(fname, "rb") as fp:
                content = base64.b64encode(fp.read()).decode()
        ret.append({'path': fname, 'content': content,
                    'encoding': 'base64'})
    return ret

# vi: ts=4 expandtab syntax=python
