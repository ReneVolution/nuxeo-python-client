# coding: utf-8
from __future__ import unicode_literals

from .compat import quote, text
from .endpoint import APIEndpoint
from .models import Batch, Blob, FileBlob
from .utils import SwapAttr

try:
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from typing import Any, Dict, List, Optional, Text, Union
        from .client import NuxeoClient
except ImportError:
    pass


class API(APIEndpoint):
    def __init__(self, client, endpoint='upload', headers=None):
        # type: (NuxeoClient, Text, Optional[Dict[Text, Text]]) -> None
        super(API, self).__init__(
            client, endpoint=endpoint, cls=Blob, headers=headers)

    def get(self, batch_id, file_idx=None):
        # type: (Text, Optional[int]) -> Union[List[Blob], Blob]
        """
        Get the detail of a batch.

        If file_idx is None, returns the details of all its blobs,
        otherwise returns the details of the corresponding blob.

        :param batch_id: the id of the batch
        :param file_idx: the index of the blob
        :return: the batch details
        """
        request_path = batch_id
        if file_idx is not None:
            request_path = '{}/{}'.format(request_path, file_idx)

        resource = super(API, self).get(path=request_path)

        if file_idx is not None:
            resource.batch_id = batch_id
            resource.fileIdx = file_idx
        return resource

    def post(self):
        # type: () -> Batch
        """
        Create a batch.

        :return: the created batch
        """
        with SwapAttr(self, '_cls', Batch):
            batch = super(API, self).post()
        return batch

    batch = post  # Alias for clarity

    def put(self, **kwargs):
        # type: (Any) -> None
        raise NotImplementedError

    def delete(self, batch_id, file_idx=None):
        # type: (Text, Optional[int]) -> None
        """
        Delete a batch or a blob.

        If the file_idx is None, deletes the batch,
        otherwise deletes the corresponding blob.

        :param batch_id: the id of the batch
        :param file_idx: the index of the blob
        :return: the deleted batch, or None for a blob
        """
        if file_idx:
            target = '{}/{}'.format(batch_id, file_idx)
            super(API, self).delete(target)
        else:
            target = batch_id
            with SwapAttr(self, '_cls', Batch):
                super(API, self).delete(target)

    def upload(self, batch, blob):
        # type: (Batch, Blob) -> Blob
        """
        Upload a blob.

        :param batch: batch of the upload
        :param blob: blob to upload
        :return: uploaded blob details
        """
        headers = self.headers
        headers.update({
            'Cache-Control': 'no-cache',
            'X-File-Name': quote(blob.name),
            'X-File-Size': text(blob.size),
            'X-File-Type': blob.mimetype,
            'Content-Length': text(blob.size),
        })

        request_path = '{}/{}'.format(batch.batchId, batch.upload_idx)
        try:
            response = super(API, self).post(
                resource=blob.data,
                path=request_path,
                raw=True,
                headers=headers
            )
        finally:
            if isinstance(blob, FileBlob):
                blob.fd.close()
        batch.upload_idx += 1
        response.batch_id = batch.uid
        return response