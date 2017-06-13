# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from unittest import main
from tempfile import mkdtemp, mkstemp
from os.path import exists, isdir
from os import remove, close
from shutil import rmtree
from json import dumps

from skbio.stats.distance import randdm
from skbio import OrdinationResults
from qiita_client import ArtifactInfo
from qiita_client.testing import PluginTestCase
import pandas as pd
import numpy as np

from qtp_diversity.validate import (
    _validate_distance_matrix, _validate_ordination_results, validate)


class ValidateTests(PluginTestCase):
    def setUp(self):
        self.out_dir = mkdtemp()
        self._clean_up_files = [self.out_dir]
        self.metadata = {
            '1.SKM4.640180': {'col': "doesn't really matters"},
            '1.SKB8.640193': {'col': "doesn't really matters"},
            '1.SKD8.640184': {'col': "doesn't really matters"},
            '1.SKM9.640192': {'col': "doesn't really matters"},
            '1.SKB7.640196': {'col': "doesn't really matters"}}

    def tearDown(self):
        for fp in self._clean_up_files:
            if exists(fp):
                if isdir(fp):
                    rmtree(fp)
                else:
                    remove(fp)

    def _create_distance_matrix(self, sample_ids):
        dm = randdm(len(sample_ids), sample_ids)
        fd, fp = mkstemp(suffix='.txt', dir=self.out_dir)
        close(fd)
        dm.write(fp)
        return fp

    def _create_ordination_results(self, sample_ids):
        # These values have been shamelessly copied from the tests in skbio
        eigvals = pd.Series([0.0961330159181, 0.0409418140138], ['CA1', 'CA2'])
        features = np.array([[0.408869425742, 0.0695518116298],
                             [-0.1153860437, -0.299767683538],
                             [-0.309967102571, 0.187391917117]])
        samples = np.random.rand(len(sample_ids), 2)
        features_ids = ['Species1', 'Species2', 'Species3']

        samples_df = pd.DataFrame(samples, index=sample_ids,
                                  columns=['CA1', 'CA2'])
        features_df = pd.DataFrame(features, index=features_ids,
                                   columns=['CA1', 'CA2'])

        ord_res = OrdinationResults(
            'CA', 'Correspondance Analysis', eigvals=eigvals,
            samples=samples_df, features=features_df)
        fd, fp = mkstemp(suffix='.txt', dir=self.out_dir)
        close(fd)
        ord_res.write(fp)
        return fp

    def _create_job(self, a_type, files, analysis):
        parameters = {'template': None,
                      'files': dumps(files),
                      'artifact_type': a_type,
                      'analysis': analysis}
        data = {'command': dumps(['Diversity types', '0.1.0', 'Validate']),
                'parameters': dumps(parameters),
                'status': 'running'}
        job_id = self.qclient.post(
            '/apitest/processing_job/', data=data)['job']
        return job_id, parameters

    def test_validate_distance_matrix(self):
        # Create a distance matrix
        sample_ids = ['1.SKM4.640180', '1.SKB8.640193', '1.SKD8.640184',
                      '1.SKM9.640192', '1.SKB7.640196']
        dm_fp = self._create_distance_matrix(sample_ids)

        # Test success
        obs_success, obs_ainfo, obs_error = _validate_distance_matrix(
            {'plain_text': [dm_fp]}, self.metadata, self.out_dir)
        self.assertTrue(obs_success)
        exp_ainfo = [ArtifactInfo(None, "distance_matrix",
                                  [(dm_fp, 'plain_text')])]
        self.assertEqual(obs_ainfo, exp_ainfo)
        self.assertEqual(obs_error, "")

        # Test failure
        sample_ids = ['1.SKM4.640180', '1.SKB8.640193', '1.SKD8.640184',
                      '1.SKM9.640192', 'NotASample']
        dm_fp = self._create_distance_matrix(sample_ids)
        obs_success, obs_ainfo, obs_error = _validate_distance_matrix(
            {'plain_text': [dm_fp]}, self.metadata, self.out_dir)
        self.assertFalse(obs_success)
        self.assertIsNone(obs_ainfo)
        self.assertEqual(obs_error, "The distance matrix contain samples not "
                                    "present in the metadata")

    def test_validate_ordination_results(self):
        # Create the ordination results
        sample_ids = ['1.SKM4.640180', '1.SKB8.640193', '1.SKD8.640184',
                      '1.SKM9.640192', '1.SKB7.640196']
        ord_res_fp = self._create_ordination_results(sample_ids)

        # Test success
        obs_success, obs_ainfo, obs_error = _validate_ordination_results(
            {'plain_text': [ord_res_fp]}, self.metadata, self.out_dir)
        self.assertTrue(obs_success)
        exp_ainfo = [ArtifactInfo(None, "ordination_results",
                     [(ord_res_fp, 'plain_text')])]
        self.assertEqual(obs_ainfo, exp_ainfo)
        self.assertEqual(obs_error, "")

        # Test failure
        sample_ids = ['1.SKM4.640180', '1.SKB8.640193', '1.SKD8.640184',
                      '1.SKM9.640192', 'NotASample']
        ord_res_fp = self._create_ordination_results(sample_ids)
        obs_success, obs_ainfo, obs_error = _validate_ordination_results(
            {'plain_text': [ord_res_fp]}, self.metadata, self.out_dir)
        self.assertFalse(obs_success)
        self.assertIsNone(obs_ainfo)
        self.assertEqual(obs_error, "The ordination results contain samples "
                                    "not present in the metadata")

    def test_validate(self):
        # Test artifact type error
        job_id, params = self._create_job(
            'NotAType', {'plan_text': 'Will fail before checking this'}, 1)
        obs_success, obs_ainfo, obs_error = validate(
            self.qclient, job_id, params, self.out_dir)
        self.assertFalse(obs_success)
        self.assertIsNone(obs_ainfo)
        self.assertEqual(
            obs_error, "Unknown artifact type NotAType. Supported types: "
                       "distance_matrix, ordination_results")

        # Test missing metadata error - to be fair, I don't know how this error
        # can happen in the live system, but better be safe than sorry
        job_id, params = self._create_job(
            'distance_matrix', {'plan_text': 'Will fail before checking this'},
            None)
        obs_success, obs_ainfo, obs_error = validate(
            self.qclient, job_id, params, self.out_dir)
        self.assertFalse(obs_success)
        self.assertIsNone(obs_ainfo)
        self.assertEqual(
            obs_error, "Missing metadata information")

        # Test distance matrix success
        sample_ids = ['1.SKM4.640180', '1.SKB8.640193', '1.SKD8.640184',
                      '1.SKM9.640192', '1.SKB7.640196']
        dm_fp = self._create_distance_matrix(sample_ids)
        job_id, params = self._create_job(
            'distance_matrix', {'plain_text': [dm_fp]}, 1)
        obs_success, obs_ainfo, obs_error = validate(
            self.qclient, job_id, params, self.out_dir)
        self.assertTrue(obs_success)
        exp_ainfo = [ArtifactInfo(None, "distance_matrix",
                                  [(dm_fp, 'plain_text')])]
        self.assertEqual(obs_ainfo, exp_ainfo)
        self.assertEqual(obs_error, "")

        # Test ordination results success
        ord_res_fp = self._create_ordination_results(sample_ids)
        job_id, params = self._create_job(
            'ordination_results', {'plain_text': [ord_res_fp]}, 1)
        obs_success, obs_ainfo, obs_error = validate(
            self.qclient, job_id, params, self.out_dir)
        self.assertTrue(obs_success)
        exp_ainfo = [ArtifactInfo(None, "ordination_results",
                     [(ord_res_fp, 'plain_text')])]
        self.assertEqual(obs_ainfo, exp_ainfo)
        self.assertEqual(obs_error, "")

if __name__ == '__main__':
    main()
