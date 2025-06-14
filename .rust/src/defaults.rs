//! Default configuration values for the workflow system.
//!
//! This module contains compile-time constants used as default values
//! throughout the workflow orchestration system.

/// Maximum number of jobs that can run in parallel
pub const MAX_JOB_PARALLEL: usize = 2;

/// Maximum number of stages that can run in parallel within a single job
pub const MAX_STAGE_PARALLEL: usize = 4;

/// Default timeout for operations in seconds (1 hour)
pub const DEFAULT_TIMEOUT: u64 = 3600;

/// Minimum interval between scheduled cron jobs in seconds (1 minute)
pub const MIN_CRON_INTERVAL: u64 = 60;

/// Default retry attempts for failed operations
pub const DEFAULT_RETRY_ATTEMPTS: u32 = 3;

/// Default retry delay in seconds
pub const DEFAULT_RETRY_DELAY: f64 = 1.0;

/// Default backoff multiplier for retry delays
pub const DEFAULT_RETRY_BACKOFF: f64 = 2.0;

/// Default maximum retry delay in seconds
pub const DEFAULT_MAX_RETRY_DELAY: f64 = 60.0;

/// Default audit retention period in days
pub const DEFAULT_AUDIT_RETENTION_DAYS: u32 = 30;

/// Default health check interval in seconds
pub const DEFAULT_HEALTH_CHECK_INTERVAL: f64 = 30.0;

/// Default health check timeout in seconds
pub const DEFAULT_HEALTH_CHECK_TIMEOUT: f64 = 10.0;

/// Default number of health check retries before marking as unhealthy
pub const DEFAULT_HEALTH_CHECK_RETRIES: u32 = 3;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_constants_are_positive() {
        assert!(MAX_JOB_PARALLEL > 0);
        assert!(MAX_STAGE_PARALLEL > 0);
        assert!(DEFAULT_TIMEOUT > 0);
        assert!(MIN_CRON_INTERVAL > 0);
        assert!(DEFAULT_RETRY_ATTEMPTS > 0);
        assert!(DEFAULT_RETRY_DELAY >= 0.0);
        assert!(DEFAULT_RETRY_BACKOFF >= 1.0);
        assert!(DEFAULT_MAX_RETRY_DELAY > 0.0);
        assert!(DEFAULT_AUDIT_RETENTION_DAYS > 0);
        assert!(DEFAULT_HEALTH_CHECK_INTERVAL > 0.0);
        assert!(DEFAULT_HEALTH_CHECK_TIMEOUT > 0.0);
        assert!(DEFAULT_HEALTH_CHECK_RETRIES > 0);
    }

    #[test]
    fn test_retry_constraints() {
        assert!(DEFAULT_RETRY_BACKOFF >= 1.0);
        assert!(DEFAULT_MAX_RETRY_DELAY >= DEFAULT_RETRY_DELAY);
    }

    #[test]
    fn test_health_check_constraints() {
        assert!(DEFAULT_HEALTH_CHECK_TIMEOUT < DEFAULT_HEALTH_CHECK_INTERVAL);
    }
}
