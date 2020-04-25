#    Copyright 2013 Red Hat, Inc
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

from oslo_db import exception as db_exc
from oslo_db.sqlalchemy import utils as sqlalchemyutils
from oslo_utils import versionutils
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import asc
from sqlalchemy.sql import true

import gosbs.conf
from gosbs.db.sqlalchemy import api as db_api
from gosbs.db.sqlalchemy.api import require_context
from gosbs.db.sqlalchemy import models
from gosbs import exception
from gosbs import objects
from gosbs.objects import base
from gosbs.objects import fields

CONF = gosbs.conf.CONF

def _dict_with_extra_specs(model):
    extra_specs = {}
    return dict(model, extra_specs=extra_specs)


@db_api.main_context_manager.writer
def _local_binary_create(context, values):
    db_local_binary = models.LocalBinarys()
    db_local_binary.update(values)

    try:
        db_local_binary.save(context.session)
    except db_exc.DBDuplicateEntry as e:
        if 'local_binaryid' in e.columns:
            raise exception.ImagesIdExists(local_binary_id=values['local_binaryid'])
        raise exception.ImagesExists(name=values['name'])
    except Exception as e:
        raise db_exc.DBError(e)

    return _dict_with_extra_specs(db_local_binary)


@db_api.main_context_manager.writer
def _local_binary_destroy(context, local_binary_id=None, local_binaryid=None):
    query = context.session.query(models.LocalBinarys)

    if local_binary_id is not None:
        query.filter(models.LocalBinarys.id == local_binary_id).delete()
    else:
        query.filter(models.LocalBinarys.id == local_binaryid).delete()


# TODO(berrange): Remove NovaObjectDictCompat
# TODO(mriedem): Remove NovaPersistentObject in version 2.0
@base.NovaObjectRegistry.register
class LocalBinary(base.NovaObject, base.NovaObjectDictCompat, base.NovaPersistentObject2):
    # Version 1.0: Initial version

    VERSION = '1.0'

    fields = {
        'uuid': fields.UUIDField(),
        'project_uuid': fields.UUIDField(),
        'service_uuid': fields.UUIDField(),
        'name': fields.StringField(),
        'checksum' : fields.StringField(),
        'ebuild_uuid': fields.UUIDField(),
        'looked' : fields.BooleanField(),
        }

    def __init__(self, *args, **kwargs):
        super(LocalBinary, self).__init__(*args, **kwargs)
        self._orig_extra_specs = {}
        self._orig_local_binary = []

    def obj_make_compatible(self, primitive, target_version):
        super(LocalBinary, self).obj_make_compatible(primitive, target_version)
        target_version = versionutils.convert_version_to_tuple(target_version)


    @staticmethod
    def _from_db_object(context, local_binary, db_local_binary, expected_attrs=None):
        if expected_attrs is None:
            expected_attrs = []
        local_binary._context = context
        for name, field in local_binary.fields.items():
            value = db_local_binary[name]
            if isinstance(field, fields.IntegerField):
                value = value if value is not None else 0
            local_binary[name] = value
        
        local_binary.obj_reset_changes()
        return local_binary

    @staticmethod
    @db_api.main_context_manager.reader
    def _local_binary_get_query_from_db(context):
        query = context.session.query(models.LocalBinarys)
        return query

    @staticmethod
    @require_context
    def _local_binary_get_from_db(context, id):
        """Returns a dict describing specific local_binarys."""
        result = LocalBinary._local_binary_get_query_from_db(context).\
                        filter_by(id=id).\
                        first()
        if not result:
            raise exception.ImagesNotFound(local_binary_id=id)
        return result

    @staticmethod
    @require_context
    def _local_binary_get_from_db(context, id):
        """Returns a dict describing specific local_binaryss."""
        result = LocalBinary._local_binary_get_query_from_db(context).\
                        filter_by(id=id).\
                        first()
        if not result:
            raise exception.ImagesNotFound(local_binary_id=id)
        return result

    @staticmethod
    @require_context
    def _local_binarys_get_by_name_from_db(context, name):
        """Returns a dict describing specific flavor."""
        result = LocalBinary._local_binary_get_query_from_db(context).\
                            filter_by(name=name).\
                            first()
        if not result:
            raise exception.FlavorNotFoundByName(local_binarys_name=name)
        return _dict_with_extra_specs(result)

    @staticmethod
    @require_context
    def _local_binary_get_by_uuid_from_db(context, uuid):
        """Returns a dict describing specific flavor."""
        result = LocalBinary._local_binary_get_query_from_db(context).\
                            filter_by(project_uuid=uuid).\
                            first()
        if not result:
            raise exception.FlavorNotFoundByName(local_binarys_name=name)
        return _dict_with_extra_specs(result)

    def obj_reset_changes(self, fields=None, recursive=False):
        super(LocalBinary, self).obj_reset_changes(fields=fields,
                recursive=recursive)

    def obj_what_changed(self):
        changes = super(LocalBinary, self).obj_what_changed()
        return changes

    @base.remotable_classmethod
    def get_by_id(cls, context, id):
        db_local_binary = cls._local_binary_get_from_db(context, id)
        return cls._from_db_object(context, cls(context), db_local_binary,
                                   expected_attrs=[])
    @base.remotable_classmethod
    def get_by_name(cls, context, name):
        db_local_binary = cls._local_binary_get_by_name_from_db(context, name)
        return cls._from_db_object(context, cls(context), db_local_binary,
                                   expected_attrs=[])
    @base.remotable_classmethod
    def get_by_uuid(cls, context, uuid):
        db_local_binary = cls._local_binary_get_by_uuid_from_db(context, uuid)
        return cls._from_db_object(context, cls(context), db_local_binary,
                                   expected_attrs=[])

    @staticmethod
    def _local_binary_create(context, updates):
        return _local_binary_create(context, updates)

    #@base.remotable
    def create(self, context):
        #if self.obj_attr_is_set('id'):
        #    raise exception.ObjectActionError(action='create',
        #reason='already created')
        updates = self.obj_get_changes()
        db_local_binary = self._local_binary_create(context, updates)
        self._from_db_object(context, self, db_local_binary)


    # NOTE(mriedem): This method is not remotable since we only expect the API
    # to be able to make updates to a local_binaryss.
    @db_api.main_context_manager.writer
    def _save(self, context, values):
        db_local_binary = context.session.query(models.LocalBinarys).\
            filter_by(id=self.id).first()
        if not db_local_binary:
            raise exception.ImagesNotFound(local_binary_id=self.id)
        db_local_binary.update(values)
        db_local_binary.save(context.session)
        # Refresh ourselves from the DB object so we get the new updated_at.
        self._from_db_object(context, self, db_local_binary)
        self.obj_reset_changes()

    def save(self, context):
        updates = self.obj_get_changes()
        if updates:
            self._save(context, updates)

    @staticmethod
    def _local_binary_destroy(context, local_binary_id=None, local_binaryid=None):
        _local_binary_destroy(context, local_binary_id=local_binary_id, local_binaryid=local_binaryid)

    #@base.remotable
    def destroy(self, context):
        # NOTE(danms): Historically the only way to delete a local_binaryss
        # is via name, which is not very precise. We need to be able to
        # support the light construction of a local_binaryss object and subsequent
        # delete request with only our name filled out. However, if we have
        # our id property, we should instead delete with that since it's
        # far more specific.
        if 'id' in self:
            self._local_binary_destroy(context, local_binary_id=self.id)
        else:
            self._local_binary_destroy(context, local_binaryid=self.local_binaryid)
        #self._from_db_object(context, self, db_local_binary)

    @base.remotable_classmethod
    def get_by_filters_first(cls, context, filters=None):
        filters = filters or {}
        db_local_binary = LocalBinary._local_binary_get_query_from_db(context)
    
        if 'status' in filters:
            db_local_binary = db_local_binary.filter(
                models.LocalBinarys.status == filters['status']).first()
        return cls._from_db_object(context, cls(context), db_local_binary,
                                   expected_attrs=[])


@db_api.main_context_manager
def _local_binary_get_all_from_db(context, inactive, filters, sort_key, sort_dir,
                            limit, marker):
    """Returns all local_binarys.
    """
    filters = filters or {}

    query = LocalBinary._local_binary_get_query_from_db(context)

    if 'ebuild_uuid' in filters:
            query = query.filter(
                models.LocalBinarys.ebuild_uuid == filters['ebuild_uuid'])
    if 'project_uuid' in filters:
            query = query.filter(
                models.LocalBinarys.project_uuid == filters['project_uuid'])
    if 'service_uuid' in filters:
            query = query.filter(
                models.LocalBinarys.service_uuid == filters['service_uuid'])

    marker_row = None
    if marker is not None:
        marker_row = LocalBinary._local_binary_get_query_from_db(context).\
                    filter_by(id=marker).\
                    first()
        if not marker_row:
            raise exception.MarkerNotFound(marker=marker)

    query = sqlalchemyutils.paginate_query(query, models.LocalBinarys,
                                           limit,
                                           [sort_key, 'uuid'],
                                           marker=marker_row,
                                           sort_dir=sort_dir)
    return [_dict_with_extra_specs(i) for i in query.all()]


@base.NovaObjectRegistry.register
class LocalBinaryList(base.ObjectListBase, base.NovaObject):
    VERSION = '1.0'

    fields = {
        'objects': fields.ListOfObjectsField('LocalBinary'),
        }

    @base.remotable_classmethod
    def get_all(cls, context, inactive=False, filters=None,
                sort_key='uuid', sort_dir='asc', limit=None, marker=None):
        db_local_binarys = _local_binary_get_all_from_db(context,
                                                 inactive=inactive,
                                                 filters=filters,
                                                 sort_key=sort_key,
                                                 sort_dir=sort_dir,
                                                 limit=limit,
                                                 marker=marker)
        return base.obj_make_list(context, cls(context), objects.local_binary.LocalBinary,
                                  db_local_binarys,
                                  expected_attrs=[])

    @db_api.main_context_manager.writer
    def destroy_all(context):
        context.session.query(models.LocalBinarys).delete()

    @db_api.main_context_manager.writer
    def update_all(context):
        values = {'status': 'waiting', }
        db_local_binary = context.session.query(models.LocalBinarys).filter_by(auto=True)
        db_local_binary.update(values)
