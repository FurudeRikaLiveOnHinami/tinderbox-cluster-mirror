# Copyright 2016 IBM Corporation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_utils import importutils

import gosbs.conf

profiler = importutils.try_import('osprofiler.profiler')

CONF = gosbs.conf.CONF

def get_traced_meta():
    if profiler and 'profiler' in CONF and CONF.profiler.enabled:
        return profiler.TracedMeta
    else:
        # NOTE(rpodolyaka): if we do not return a child of type, then Python
        # fails to build a correct MRO when osprofiler is not installed
        class NoopMeta(type):
            pass
        return NoopMeta


def trace_cls(name, **kwargs):
    """Wrap the OSProfiler trace_cls decorator so that it will not try to
    patch the class unless OSProfiler is present and enabled in the config

    :param name: The name of action. E.g. wsgi, rpc, db, etc..
    :param kwargs: Any other keyword args used by profiler.trace_cls
    """

    def decorator(cls):
        if profiler and 'profiler' in CONF and CONF.profiler.enabled:
            trace_decorator = profiler.trace_cls(name, kwargs)
            return trace_decorator(cls)
        return cls

    return decorator
