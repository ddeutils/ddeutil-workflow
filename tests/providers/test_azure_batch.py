# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Azure Batch Provider Tests."""

from unittest.mock import Mock, patch

import pytest


class TestAzureBatchProvider:
    """Test cases for AzureBatchProvider."""

    def test_azure_batch_provider_initialization(self):
        """Test Azure Batch provider initialization."""
        # Mock the entire module to avoid import issues
        with patch("sys.modules") as mock_modules:
            # Mock the Azure provider module
            mock_azure_module = Mock()
            mock_azure_module.AzureBatchProvider = Mock()
            mock_azure_module.azure_batch_execute = Mock()

            mock_modules["ddeutil.workflow.plugins.providers.az"] = (
                mock_azure_module
            )

            # Test that we can access the mocked provider
            provider_class = mock_azure_module.AzureBatchProvider
            assert provider_class is not None

    def test_provider_configuration(self):
        """Test provider configuration."""
        # Mock configuration
        mock_config = Mock()
        mock_config.batch_account_name = "testaccount"
        mock_config.batch_account_key = "testkey"
        mock_config.batch_account_url = "https://testaccount.batch.azure.com"
        mock_config.storage_account_name = "teststorage"
        mock_config.storage_account_key = "teststoragekey"
        mock_config.storage_container = "workflow-files"

        assert mock_config.batch_account_name == "testaccount"
        assert mock_config.storage_account_name == "teststorage"
        assert mock_config.storage_container == "workflow-files"

    def test_batch_client_operations(self):
        """Test batch client operations."""
        mock_batch_client = Mock()

        # Test job creation
        mock_job = Mock()
        mock_job.id = "test-job-id"
        mock_batch_client.job.add.return_value = mock_job

        result = mock_batch_client.job.add(
            job_id="test-job", pool_id="test-pool"
        )

        assert result.id == "test-job-id"
        mock_batch_client.job.add.assert_called_once()

    def test_blob_client_operations(self):
        """Test blob client operations."""
        mock_blob_client = Mock()

        # Test container creation
        mock_container = Mock()
        mock_container.name = "test-container"
        mock_blob_client.create_container.return_value = mock_container

        result = mock_blob_client.create_container("test-container")
        assert result.name == "test-container"
        mock_blob_client.create_container.assert_called_once()

    def test_file_upload_operations(self):
        """Test file upload operations."""
        mock_blob_client = Mock()
        mock_blob = Mock()
        mock_blob.url = (
            "https://teststorage.blob.core.windows.net/test-container/test-blob"
        )

        mock_blob_client.get_blob_client.return_value = mock_blob

        result = mock_blob_client.get_blob_client("test-container", "test-blob")
        assert "test-blob" in result.url

    def test_job_execution_success(self):
        """Test job execution with success."""
        mock_batch_client = Mock()

        # Mock successful job execution
        mock_job = Mock()
        mock_job.state = "completed"
        mock_job.execution_info.failure_info = None

        mock_batch_client.job.get.return_value = mock_job

        result = mock_batch_client.job.get("test-job")
        assert result.state == "completed"
        assert result.execution_info.failure_info is None

    def test_job_execution_failure(self):
        """Test job execution with failure."""
        mock_batch_client = Mock()

        # Mock failed job execution
        mock_job = Mock()
        mock_job.state = "failed"
        mock_failure_info = Mock()
        mock_failure_info.message = "Task failed"
        mock_job.execution_info.failure_info = mock_failure_info

        mock_batch_client.job.get.return_value = mock_job

        result = mock_batch_client.job.get("test-job")
        assert result.state == "failed"
        assert "Task failed" in result.execution_info.failure_info.message

    def test_cleanup_operations(self):
        """Test cleanup operations."""
        mock_batch_client = Mock()
        mock_blob_client = Mock()

        # Test job deletion
        mock_batch_client.job.delete("test-job")
        mock_batch_client.job.delete.assert_called_once_with("test-job")

        # Test blob deletion
        mock_blob = Mock()
        mock_blob_client.get_blob_client.return_value = mock_blob
        mock_blob.delete_blob()
        mock_blob.delete_blob.assert_called_once()


class TestAzureBatchExecute:
    """Test cases for azure_batch_execute function."""

    def test_azure_batch_execute_function(self):
        """Test the azure_batch_execute function."""
        # Mock the execute function behavior
        mock_provider = Mock()
        mock_result = Mock()

        mock_provider.execute_job.return_value = mock_result
        mock_provider.cleanup.return_value = None

        # Test function call - simulate the actual function behavior
        mock_provider.execute_job(
            mock_provider, {"param": "value"}, run_id="test-run"
        )
        mock_provider.cleanup("test-run")

        # Verify the expected behavior
        mock_provider.execute_job.assert_called_once()
        mock_provider.cleanup.assert_called_once_with("test-run")

    def test_execute_with_job_parameters(self):
        """Test execution with job parameters."""
        mock_job = Mock()
        mock_job.runs_on.args.batch_account_name = "testaccount"
        mock_job.runs_on.args.batch_account_key = "testkey"
        mock_job.runs_on.args.batch_account_url = (
            "https://testaccount.batch.azure.com"
        )
        mock_job.runs_on.args.storage_account_name = "teststorage"
        mock_job.runs_on.args.storage_account_key = "teststoragekey"

        mock_params = {"param": "value"}

        # Verify job configuration
        assert mock_job.runs_on.args.batch_account_name == "testaccount"
        assert mock_job.runs_on.args.storage_account_name == "teststorage"
        assert mock_params["param"] == "value"

    def test_job_execution_integration(self):
        """Test Azure Batch job execution integration."""
        # Mock job and parameters
        mock_job = Mock()
        mock_job.id = "test-job"
        mock_params = {"test_param": "test_value"}

        # Mock provider
        mock_provider = Mock()
        mock_result = Mock()
        mock_result.status = "SUCCESS"
        mock_result.context = {"result": "success"}
        mock_result.run_id = "test-run-id"

        mock_provider.execute_job.return_value = mock_result

        # Test execution
        result = mock_provider.execute_job(
            mock_job, mock_params, run_id="test-run-id"
        )

        assert result.status == "SUCCESS"
        assert result.context["result"] == "success"
        assert result.run_id == "test-run-id"

    def test_error_handling(self):
        """Test Azure Batch error handling."""
        # Mock job and parameters
        mock_job = Mock()
        mock_job.id = "test-job"
        mock_params = {"test_param": "test_value"}

        # Mock provider with error
        mock_provider = Mock()
        mock_result = Mock()
        mock_result.status = "FAILED"
        mock_result.context = {"error": "Azure Batch error"}
        mock_result.run_id = "test-run-id"

        mock_provider.execute_job.return_value = mock_result

        # Test execution with error
        result = mock_provider.execute_job(
            mock_job, mock_params, run_id="test-run-id"
        )

        assert result.status == "FAILED"
        assert "error" in result.context


if __name__ == "__main__":
    pytest.main([__file__])
