# coding: utf-8
from __future__ import unicode_literals

import json
import os

import pytest
import requests
from requests.exceptions import ConnectionError

from nuxeo import constants
from nuxeo.auth import TokenAuth
from nuxeo.compat import get_bytes, long, text
from nuxeo.exceptions import BadQuery, HTTPError, Unauthorized
from nuxeo.models import Blob, User
from nuxeo.utils import SwapAttr


@pytest.mark.parametrize('method, params, is_valid', [
    # 'file' type in (Blob, str)
    ('Document.SetBlob', {'file': Blob()}, True),
    ('Document.SetBlob', {'file': 'test.txt'}, True),
    ('Document.SetBlob', {'file': 0}, False),
    # 'blockInheritance' type == boolean
    ('Document.AddPermission', {'permission': 'Read',
                                'blockInheritance': False}, True),
    ('Document.AddPermission', {'permission': 'Read',
                                'blockInheritance': 'false'}, False),
    # 'end' type == str
    ('Document.AddPermission',
        {'permission': 'Read', 'end': '01-01-2018'}, True),
    ('Document.AddPermission', {'permission': 'Read', 'end': True}, False),
    # 'value' type == str
    ('Document.Fetch', {'value': 'test.txt'}, True),
    ('Document.Fetch', {'value': True}, False),
    # 'target' type == list
    ('Document.MultiPublish', {'target': ['test1.txt', 'test2.txt']}, True),
    ('Document.MultiPublish', {'target': 0}, False),
    # 'pageNo' type == int
    ('Audit.Query', {'query': 'test', 'pageNo': 100}, True),
    # 'pageSize' type == int
    ('Audit.Query', {'query': 'test', 'pageNo': 'test'}, False),
    ('Document.Query', {'query': 'test', 'pageSize': 10}, True),
    ('Document.Query', {'query': 'test', 'pageSize': 'test'}, False),
    # 'startPage', 'endPage' type == long
    ('PDF.ExtractPages', {'startPage': 1, 'endPage': long(2)}, True),
    ('PDF.ExtractPages', {'startPage': 'test', 'endPage': 'test'}, False),
    # 'info' type == dict
    ('User.Invite', {'info': {'username': 'test'}}, True),
    ('User.Invite', {'info': 0}, False),
    # 'properties' type == dict
    ('Document.Create', {'type': 'Document',
                         'properties': {'dc:title': 'test'}}, True),
    ('Document.Create', {'type': 'Document', 'properties': 0}, False),
    # 'file' type == str
    ('Blob.Create', {'file': 'test.txt'}, True),
    ('Blob.Create', {'file': 0}, False),
    # 'value' type == Sequence
    ('Document.SetProperty', {'xpath': 'test', 'value': 'test'}, True),
    ('Document.SetProperty', {'xpath': 'test', 'value': [0, 1, 2]}, True),
    ('Document.SetProperty', {'xpath': 'test', 'value': 0}, False),
    # 'query' type == str
    ('Document.Query', {'query': 'test'}, True),
    ('Document.Query', {'query': 0}, False),
    # 'queryParams' type in [list, str]
    ('Document.Query', {'query': 'test',
                        'queryParams': ['a', 'b', 'c']}, True),
    ('Document.Query', {'query': 'test', 'queryParams': 'test'}, True),
    ('Document.Query', {'query': 'test', 'queryParams': 0}, False),
    # 'queryParams' is also optional, None should be accepted
    ('Document.Query', {'query': 'test',
                        'queryParams': None}, True),
    # 'validationMethod' type == str
    ('User.Invite', {'validationMethod': 'test'}, True),
    ('User.Invite', {'validationMethod': 0}, False),
    # unknown param
    ('Document.Query', {'alien': 'alien'}, False),
])
def test_check_params(method, params, is_valid, server):
    if is_valid:
        server.operations.check_params(method, params)
    else:
        with pytest.raises(BadQuery):
            server.operations.check_params(method, params)


def test_check_params_constant(server):
    operation = server.operations.new('Document.GetChild')
    operation.params = {'name': 'workspaces', 'alien': 'the return'}
    operation.input_obj = '/default-domain'

    # Should not fail here
    assert not constants.CHECK_PARAMS
    operation.execute()

    # But should fail now
    with SwapAttr(constants, 'CHECK_PARAMS', True):
        with pytest.raises(BadQuery):
            operation.execute()


def test_check_params_unknown_operation(server):
    with pytest.raises(BadQuery):
        server.operations.check_params('alien', {})


def test_encoding_404_error(server):
    with SwapAttr(server.client, 'host', 'http://localhost:8080/'):
        with pytest.raises((ConnectionError, HTTPError)) as e:
            server.documents.get(path='/')
        if isinstance(e, HTTPError):
            assert e.value.status == 404


def test_handle_error(server):
    err = ValueError('test')
    err_handled = server.client._handle_error(err)
    assert err == err_handled


def test_file_out(server):
    operation = server.operations.new('Document.GetChild')
    operation.params = {'name': 'workspaces'}
    operation.input_obj = '/default-domain'

    from logging import getLogger
    log = getLogger(__name__)

    def check_suspended(msg):
        log.info('Check suspended: %s', msg)

    def unlock_path(path):
        log.info('Unlock path: %s', path)
        return True

    def lock_path(path, locker):
        log.info('Lock path: %s, %s', path, locker)

    file_out = operation.execute(
        file_out='test', check_suspended=check_suspended,
        lock_path=lock_path, unlock_path=unlock_path)

    with open(file_out) as f:
        file_content = json.loads(f.read())
        resp_content = operation.execute()
        assert file_content == resp_content
    os.remove(file_out)


def test_get_operations(server):
    assert server.operations


def test_query(server):
    search = server.client.query('SELECT * FROM Domain')
    assert search['entries']


def test_query_empty(server):
    query = 'SELECT * FROM Document WHERE uid = "non-existant-ahah"'
    params = {'properties': '*'}
    search = server.client.query(query, params=params)
    assert not search.get('entries')


def test_server_info(server):
    # At start, no server information
    with pytest.raises(AttributeError):
        server.client._server_info

    # First call
    assert server.client.server_info()
    assert isinstance(server.client.server_info(), dict)

    # Force the call
    server.client._server_info = None
    assert server.client.server_info(force=True)
    assert server.client.server_info() == server.client.server_info(force=True)

    # Bad call
    server.client._server_info = None
    with SwapAttr(server.client, 'host', 'http://example.org/'):
        assert not server.client.server_info()


def test_server_version(server):
    assert server.client.server_version
    assert str(server.client)

    # Bad call
    server.client._server_info = None
    with SwapAttr(server.client, 'host', 'http://example.org/'):
        assert not server.client.server_version


def test_set_repository(server):
    server.client.set(repository='foo')
    assert server.documents._path(uid='1234') == 'repo/foo/id/1234'
    server.client.set(repository='default')


def test_request_token(server):
    app_name = 'Nuxeo Drive'
    device_id = '41f0711a-f008-4c11-b3f1-c5bddcb50d77'
    device = 'GNU/Linux'
    permission = 'ReadWrite'

    prev_auth = server.client.auth
    try:
        token = server.client.request_auth_token(
            device_id, permission, app_name=app_name, device=device)
        assert server.client.auth.token == token
        assert server.client.auth == TokenAuth(token)
        assert server.client.auth != TokenAuth('0')
        assert server.client.is_reachable()

        # Calling twice should return the same token
        same_token = server.client.request_auth_token(
            device_id, permission, app_name=app_name, device=device)
        assert token == same_token
    finally:
        server.client.auth = prev_auth


def test_send_wrong_method(server):
    with pytest.raises(BadQuery):
        server.client.request('TEST', 'example')


def test_server_reachable(server):
    assert server.client.is_reachable()
    with SwapAttr(server.client, 'host', 'http://example.org'):
        assert not server.client.is_reachable()
    assert server.client.is_reachable()


@pytest.mark.skipif(
    requests.__version__ < '2.12.2',
    reason='Requests >= 2.12.2 required for auth unicode support.')
def test_unauthorized(server):
    username = 'ミカエル'
    password = 'test'
    user = server.users.create(
        User(properties={
            'username': username,
            'password': password
        }))

    auth = server.client.auth
    server.client.auth = (get_bytes(username), password)
    try:
        with pytest.raises(Unauthorized) as e:
            server.users.create(
                User(properties={
                    'username': 'another_one',
                    'password': 'test'
                }))
        assert text(e.value)
    finally:
        server.client.auth = auth
        user.delete()
