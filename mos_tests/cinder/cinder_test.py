#    Copyright 2015 Mirantis, Inc.
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

import logging

import pytest

from mos_tests.functions.base import OpenStackTestCase
from mos_tests.functions import common as common_functions

logger = logging.getLogger(__name__)


@pytest.mark.undestructive
class CinderIntegrationTests(OpenStackTestCase):
    """Basic automated tests for OpenStack Heat verification."""

    def setUp(self):
        super(self.__class__, self).setUp()

        self.volume_list = []
        self.snapshot_list = []
        self.tenant_id = self.session.get_project_id()
        self.quota = self.cinder.quotas.get(self.tenant_id).snapshots
        self.cinder.quotas.update(self.tenant_id, snapshots=200)

    def tearDown(self):
        try:
            for snapshot in self.snapshot_list:
                common_functions.delete_volume_snapshot(self.cinder, snapshot)

            for volume in self.volume_list:
                common_functions.delete_volume(self.cinder, volume)
            self.volume_list = []
        finally:
            self.cinder.quotas.update(self.tenant_id, snapshots=self.quota)

    @pytest.mark.testrail_id('543176')
    def test_creating_multiple_snapshots(self):
        """Checks creation of several snapshot at the same time

            Steps:
                1. Create a volume
                2. Create 70 snapshots for it. Wait for creation
                3. Delete all of them
                4. Launch creation of 50 snapshot without waiting of creation
        """
        # 1. Create volume
        logger.info('Create volume')
        image = self._get_cirros_image()
        volume = common_functions.create_volume(self.cinder, image.id)
        self.volume_list.append(volume)

        # 2. Creation of 70 snapshots
        logger.info('Create 70 snapshots')
        for num in range(70):
            logger.info('Creating {} snapshot'.format(num))
            snapshot = self.cinder.volume_snapshots.create(
                volume.id,
                name='1st_creation_{0}'.format(num))
            self.snapshot_list.append(snapshot)
            self.assertTrue(common_functions.check_volume_snapshot_status(
                self.cinder, snapshot, 'available'))

        # 3. Delete all snapshots
        logger.info('Delete all snapshots')
        for snapshot in self.snapshot_list:
            self.cinder.volume_snapshots.delete(snapshot)

        common_functions.wait(lambda: len(self.cinder.volume_snapshots.findall(
                status='available', volume_id=volume.id)) == 0,
                timeout_seconds=60,
                waiting_for='snapshots to be deleted')

        self.snapshot_list = []

        # 4. Launch creation of 50 snapshot without waiting of creation
        logger.info('Launch creation of 50 snapshot without waiting '
                    'of creation')
        new_count = 50
        for num in range(new_count):
            logger.info('Creating {} snapshot'.format(num))
            snapshot = self.cinder.volume_snapshots.create(
                volume.id,
                name='2nd_creation_{0}'.format(num))
            self.snapshot_list.append(snapshot)

        def is_all_available():
            available_count = len(self.cinder.volume_snapshots.findall(
                volume_id=volume.id, status='available'))
            logger.debug('Available snapshot count: {}'.format(
                available_count))
            return available_count == new_count

        common_functions.wait(
            is_all_available,
            timeout_seconds=10 * 60,
            sleep_seconds=20,
            waiting_for='all snapshot became to available state')
