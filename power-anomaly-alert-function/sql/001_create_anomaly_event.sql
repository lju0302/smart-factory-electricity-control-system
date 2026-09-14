IF OBJECT_ID('dbo.anomaly_event', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.anomaly_event (
        alert_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        equipment_id NVARCHAR(100) NOT NULL,
        window_end_time DATETIME2 NOT NULL,
        anomaly_type NVARCHAR(100) NOT NULL,
        severity NVARCHAR(20) NOT NULL,
        metric_name NVARCHAR(100) NULL,
        metric_value FLOAT NULL,
        threshold_value FLOAT NULL,
        anomaly_score FLOAT NULL,
        rule_score FLOAT NULL,
        iforest_score FLOAT NULL,
        final_score FLOAT NULL,
        duration_minutes INT NULL,
        detection_window NVARCHAR(20) NULL,
        status NVARCHAR(20) NOT NULL DEFAULT 'OPEN',
        notification_status NVARCHAR(20) NOT NULL DEFAULT 'PENDING',
        retry_count INT NOT NULL DEFAULT 0,
        last_error_message NVARCHAR(MAX) NULL,
        message NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
        notified_at DATETIME2 NULL
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_anomaly_event_dispatch'
      AND object_id = OBJECT_ID('dbo.anomaly_event')
)
BEGIN
    CREATE INDEX IX_anomaly_event_dispatch
    ON dbo.anomaly_event (
        notification_status,
        retry_count,
        severity,
        created_at
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_anomaly_event_open'
      AND object_id = OBJECT_ID('dbo.anomaly_event')
)
BEGIN
    CREATE INDEX IX_anomaly_event_open
    ON dbo.anomaly_event (
        equipment_id,
        anomaly_type,
        status,
        window_end_time
    );
END;
GO
