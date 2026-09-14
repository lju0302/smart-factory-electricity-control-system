IF COL_LENGTH('dbo.anomaly_predictions', 'aggregation_level') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD aggregation_level NVARCHAR(20) NULL;
END;

IF COL_LENGTH('dbo.anomaly_predictions', 'rule_anomaly') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD rule_anomaly INT NULL;
END;

IF COL_LENGTH('dbo.anomaly_predictions', 'rule_score') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD rule_score FLOAT NULL;
END;

IF COL_LENGTH('dbo.anomaly_predictions', 'rule_reason') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD rule_reason NVARCHAR(MAX) NULL;
END;

IF COL_LENGTH('dbo.anomaly_predictions', 'iforest_anomaly') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD iforest_anomaly INT NULL;
END;

IF COL_LENGTH('dbo.anomaly_predictions', 'iforest_score') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD iforest_score FLOAT NULL;
END;

IF COL_LENGTH('dbo.anomaly_predictions', 'primary_anomaly_model') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD primary_anomaly_model NVARCHAR(100) NULL;
END;

IF COL_LENGTH('dbo.anomaly_predictions', 'model_vote_count') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD model_vote_count INT NULL;
END;

IF COL_LENGTH('dbo.anomaly_predictions', 'rule_contribution') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD rule_contribution FLOAT NULL;
END;

IF COL_LENGTH('dbo.anomaly_predictions', 'iforest_contribution') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD iforest_contribution FLOAT NULL;
END;

IF COL_LENGTH('dbo.anomaly_predictions', 'data_quality_issue_flag') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD data_quality_issue_flag INT NULL;
END;

IF COL_LENGTH('dbo.anomaly_predictions', 'data_quality_reason') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD data_quality_reason NVARCHAR(MAX) NULL;
END;

IF COL_LENGTH('dbo.anomaly_predictions', 'created_at') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD created_at DATETIME2 NULL;
END;

IF COL_LENGTH('dbo.anomaly_predictions', 'reference_only') IS NULL
BEGIN
    ALTER TABLE dbo.anomaly_predictions ADD reference_only BIT NULL;
END;
