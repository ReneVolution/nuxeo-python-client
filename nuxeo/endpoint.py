# coding: utf-8
from __future__ import unicode_literals

from requests import Response

from .exceptions import BadQuery, HTTPError

try:
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from typing import Any, Dict, Optional, Text, Type, Union
        from .client import NuxeoClient
        from .models import Model
except ImportError:
    pass


class APIEndpoint(object):
    """
    Represents an API endpoint for Nuxeo, containing common patterns
    for CRUD operations.
    """

    def __init__(
        self,
        client,  # type: NuxeoClient
        endpoint=None,  # type: Optional[Text]
        headers=None,  # type: Optional[Dict[Text, Text]]
        cls=None,  # type: Optional[Type]
    ):
        # type: (...) -> None
        """
        Creates an instance of the APIEndpoint class.

        :param client: the authenticated REST client
        :param endpoint: the URL path to the resource endpoint
        :param headers: the extra HTTP headers
        :param cls: the Class to use when parsing results
        """
        self.client = client
        if endpoint:
            self.endpoint = '{}/{}'.format(client.api_path, endpoint)
        else:
            self.endpoint = client.api_path
        self.headers = headers or {}
        self._cls = cls

    def get(
        self,
        path=None,  # type: Optional[Text]
        cls=None,  # type: Optional[Type]
        raw=False,  # type: bool
        single=False,  # type: bool
        **kwargs  # type: Any
    ):
        # type: (...) -> Any
        """
        Gets the details for one or more resources.

        :param path: the endpoint (URL path) for the request
        :param cls: a class to use for parsing, if different
                    than the base resource
        :param raw: if True, directly return the content of
                    the response
        :param single: if True, do not parse as list
        :return: one or more instances of cls parsed from
                 the returned JSON
        """
        endpoint = self.endpoint

        if not cls:
            cls = self._cls

        if path:
            endpoint = '{}/{}'.format(endpoint, path)

        response = self.client.request('GET', endpoint, **kwargs)

        if isinstance(response, Response):
            if raw or response.status_code == 204:
                return response.content
            json = response.json()
        else:
            return response

        if cls is dict:
            return json

        if not single and isinstance(json, dict) and 'entries' in json:
            json = json['entries']

        if isinstance(json, list):
            return [cls.parse(resource, service=self) for resource in json]

        return cls.parse(json, service=self)

    def post(self, resource=None, path=None, raw=False, **kwargs):
        # type: (Optional[Any], Optional[Text], bool, Any) -> Any
        """
        Creates a new instance of the resource.

        :param resource: the data to post
        :param path: the endpoint (URL path) for the request
        :param raw: if False, parse the outgoing data to JSON
        :return: the created resource
        """
        if resource and not raw and not isinstance(resource, dict):
            if isinstance(resource, self._cls):
                resource = resource.as_dict()
            else:
                raise BadQuery(
                    'Data must be a Model object or a dictionary.')

        endpoint = self.endpoint

        if path:
            endpoint = '{}/{}'.format(endpoint, path)

        response = self.client.request(
            'POST', endpoint, data=resource, raw=raw, **kwargs)

        if isinstance(response, dict):
            return response
        return self._cls.parse(response.json(), service=self)

    def put(self, resource=None, path=None, **kwargs):
        # type: (Optional[Model], Optional[Text], Any) -> Any
        """
        Edits an existing resource.

        :param resource: the resource instance
        :param path: the endpoint (URL path) for the request
        :return: the modified resource
        """

        endpoint = '{}/{}'.format(self.endpoint, path or resource.uid)

        data = resource.as_dict() if resource else resource

        response = self.client.request('PUT', endpoint, data=data, **kwargs)

        if resource:
            return self._cls.parse(response.json(), service=self)

    def delete(self, resource_id):
        # type: (Text) -> None
        """
        Deletes an existing resource.

        :param resource_id: the resource ID to be deleted
        """

        endpoint = '{}/{}'.format(self.endpoint, resource_id)
        self.client.request('DELETE', endpoint)

    def exists(self, path):
        # type: (Text) -> bool
        """
        Checks if a resource exists.

        :param path: the endpoint (URL path) for the request
        :return: True if it exists, else False
        """
        endpoint = '{}/{}'.format(self.endpoint, path)

        try:
            self.client.request('GET', endpoint)
            return True
        except HTTPError as e:
            if e.status != 404:
                raise e
        return False
