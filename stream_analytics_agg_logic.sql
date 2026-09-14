SELECT
    module AS equipment_id,
    CAST(DateAdd(hour, 9, System.Timestamp) AS datetime) AS window_end_time,
    AVG(CAST(voltageR AS float)) AS avg_voltage_r,
    AVG(CAST(voltageS AS float)) AS avg_voltage_s,
    AVG(CAST(voltageT AS float)) AS avg_voltage_t,
    AVG(CAST(currentR AS float)) AS avg_current_r,
    AVG(CAST(currentS AS float)) AS avg_current_s,
    AVG(CAST(currentT AS float)) AS avg_current_t,
    AVG(CAST(avg_current_r AS float), CAST(avg_current_s AS float), CAST(avg_current_t AS float)) AS avg_current,
    AVG((CAST(powerFactorR AS float) + CAST(powerFactorS AS float) + CAST(powerFactorT AS float)) / 3.0) AS avg_power_factor,
    AVG((CASE WHEN CAST(voltageR AS float) >= CAST(voltageS AS float) AND CAST(voltageR AS float) >= CAST(voltageT AS float) THEN CAST(voltageR AS float) WHEN CAST(voltageS AS float) >= CAST(voltageR AS float) AND CAST(voltageS AS float) >= CAST(voltageT AS float) THEN CAST(voltageS AS float) ELSE CAST(voltageT AS float) END - (CAST(voltageR AS float) + CAST(voltageS AS float) + CAST(voltageT AS float)) / 3.0) / NULLIF((CAST(voltageR AS float) + CAST(voltageS AS float) + CAST(voltageT AS float)) / 3.0, 0) * 100.0) AS avg_voltage_imbalance_rate,
    AVG((CASE WHEN CAST(currentR AS float) >= CAST(currentS AS float) AND CAST(currentR AS float) >= CAST(currentT AS float) THEN CAST(currentR AS float) WHEN CAST(currentS AS float) >= CAST(currentR AS float) AND CAST(currentS AS float) >= CAST(currentT AS float) THEN CAST(currentS AS float) ELSE CAST(currentT AS float) END - (CAST(currentR AS float) + CAST(currentS AS float) + CAST(currentT AS float)) / 3.0) / NULLIF((CAST(currentR AS float) + CAST(currentS AS float) + CAST(currentT AS float)) / 3.0, 0) * 100.0) AS avg_current_imbalance_rate,
    COUNT(*) AS event_count
INTO [poweroutput]
FROM [powerinput] TIMESTAMP BY StringToDateTime(CAST(localtime AS nvarchar(max)), 'yyyyMMddHHmmss')
GROUP BY module, TumblingWindow(minute, 1);

-- 15분 단위 집계
SELECT
    module AS equipment_id,
    CAST(DateAdd(hour, 9, System.Timestamp) AS datetime) AS window_end_time,
    AVG(CAST(voltageR AS float)) AS avg_voltage_r,
    AVG(CAST(voltageS AS float)) AS avg_voltage_s,
    AVG(CAST(voltageT AS float)) AS avg_voltage_t,
    AVG(CAST(currentR AS float)) AS avg_current_r,
    AVG(CAST(currentS AS float)) AS avg_current_s,
    AVG(CAST(currentT AS float)) AS avg_current_t,
    AVG((CAST(powerFactorR AS float) + CAST(powerFactorS AS float) + CAST(powerFactorT AS float)) / 3.0) AS avg_power_factor,
    AVG((CASE WHEN CAST(voltageR AS float) >= CAST(voltageS AS float) AND CAST(voltageR AS float) >= CAST(voltageT AS float) THEN CAST(voltageR AS float) WHEN CAST(voltageS AS float) >= CAST(voltageR AS float) AND CAST(voltageS AS float) >= CAST(voltageT AS float) THEN CAST(voltageS AS float) ELSE CAST(voltageT AS float) END - (CAST(voltageR AS float) + CAST(voltageS AS float) + CAST(voltageT AS float)) / 3.0) / NULLIF((CAST(voltageR AS float) + CAST(voltageS AS float) + CAST(voltageT AS float)) / 3.0, 0) * 100.0) AS avg_voltage_imbalance_rate,
    AVG((CASE WHEN CAST(currentR AS float) >= CAST(currentS AS float) AND CAST(currentR AS float) >= CAST(currentT AS float) THEN CAST(currentR AS float) WHEN CAST(currentS AS float) >= CAST(currentR AS float) AND CAST(currentS AS float) >= CAST(currentT AS float) THEN CAST(currentS AS float) ELSE CAST(currentT AS float) END - (CAST(currentR AS float) + CAST(currentS AS float) + CAST(currentT AS float)) / 3.0) / NULLIF((CAST(currentR AS float) + CAST(currentS AS float) + CAST(currentT AS float)) / 3.0, 0) * 100.0) AS avg_current_imbalance_rate,
    COUNT(*) AS event_count
INTO [poweroutput_15m]
FROM [powerinput] TIMESTAMP BY CAST(SUBSTRING(CAST(localtime AS nvarchar(max)), 1, 4) + '-' + SUBSTRING(CAST(localtime AS nvarchar(max)), 5, 2) + '-' + SUBSTRING(CAST(localtime AS nvarchar(max)), 7, 2) + ' ' + SUBSTRING(CAST(localtime AS nvarchar(max)), 9, 2) + ':' + SUBSTRING(CAST(localtime AS nvarchar(max)), 11, 2) + ':' + SUBSTRING(CAST(localtime AS nvarchar(max)), 13, 2) AS datetime)
GROUP BY module, TumblingWindow(minute, 15);

-- 1시간 단위 집계
SELECT
    module AS equipment_id,
    CAST(DateAdd(hour, 9, System.Timestamp) AS datetime) AS window_end_time,
    AVG(CAST(voltageR AS float)) AS avg_voltage_r,
    AVG(CAST(voltageS AS float)) AS avg_voltage_s,
    AVG(CAST(voltageT AS float)) AS avg_voltage_t,
    AVG(CAST(currentR AS float)) AS avg_current_r,
    AVG(CAST(currentS AS float)) AS avg_current_s,
    AVG(CAST(currentT AS float)) AS avg_current_t,
    AVG((CAST(powerFactorR AS float) + CAST(powerFactorS AS float) + CAST(powerFactorT AS float)) / 3.0) AS avg_power_factor,
    AVG((CASE WHEN CAST(voltageR AS float) >= CAST(voltageS AS float) AND CAST(voltageR AS float) >= CAST(voltageT AS float) THEN CAST(voltageR AS float) WHEN CAST(voltageS AS float) >= CAST(voltageR AS float) AND CAST(voltageS AS float) >= CAST(voltageT AS float) THEN CAST(voltageS AS float) ELSE CAST(voltageT AS float) END - (CAST(voltageR AS float) + CAST(voltageS AS float) + CAST(voltageT AS float)) / 3.0) / NULLIF((CAST(voltageR AS float) + CAST(voltageS AS float) + CAST(voltageT AS float)) / 3.0, 0) * 100.0) AS avg_voltage_imbalance_rate,
    AVG((CASE WHEN CAST(currentR AS float) >= CAST(currentS AS float) AND CAST(currentR AS float) >= CAST(currentT AS float) THEN CAST(currentR AS float) WHEN CAST(currentS AS float) >= CAST(currentR AS float) AND CAST(currentS AS float) >= CAST(currentT AS float) THEN CAST(currentS AS float) ELSE CAST(currentT AS float) END - (CAST(currentR AS float) + CAST(currentS AS float) + CAST(currentT AS float)) / 3.0) / NULLIF((CAST(currentR AS float) + CAST(currentS AS float) + CAST(currentT AS float)) / 3.0, 0) * 100.0) AS avg_current_imbalance_rate,
    COUNT(*) AS event_count
INTO [poweroutput_1h]
FROM [powerinput] TIMESTAMP BY CAST(SUBSTRING(CAST(localtime AS nvarchar(max)), 1, 4) + '-' + SUBSTRING(CAST(localtime AS nvarchar(max)), 5, 2) + '-' + SUBSTRING(CAST(localtime AS nvarchar(max)), 7, 2) + ' ' + SUBSTRING(CAST(localtime AS nvarchar(max)), 9, 2) + ':' + SUBSTRING(CAST(localtime AS nvarchar(max)), 11, 2) + ':' + SUBSTRING(CAST(localtime AS nvarchar(max)), 13, 2) AS datetime)
GROUP BY module, TumblingWindow(hour, 1);

-- 1일 단위 집계
SELECT
    module AS equipment_id,
    CAST(DateAdd(hour, 9, System.Timestamp) AS datetime) AS window_end_time,
    AVG(CAST(voltageR AS float)) AS avg_voltage_r,
    AVG(CAST(voltageS AS float)) AS avg_voltage_s,
    AVG(CAST(voltageT AS float)) AS avg_voltage_t,
    AVG(CAST(currentR AS float)) AS avg_current_r,
    AVG(CAST(currentS AS float)) AS avg_current_s,
    AVG(CAST(currentT AS float)) AS avg_current_t,
    AVG((CAST(powerFactorR AS float) + CAST(powerFactorS AS float) + CAST(powerFactorT AS float)) / 3.0) AS avg_power_factor,
    AVG((CASE WHEN CAST(voltageR AS float) >= CAST(voltageS AS float) AND CAST(voltageR AS float) >= CAST(voltageT AS float) THEN CAST(voltageR AS float) WHEN CAST(voltageS AS float) >= CAST(voltageR AS float) AND CAST(voltageS AS float) >= CAST(voltageT AS float) THEN CAST(voltageS AS float) ELSE CAST(voltageT AS float) END - (CAST(voltageR AS float) + CAST(voltageS AS float) + CAST(voltageT AS float)) / 3.0) / NULLIF((CAST(voltageR AS float) + CAST(voltageS AS float) + CAST(voltageT AS float)) / 3.0, 0) * 100.0) AS avg_voltage_imbalance_rate,
    AVG((CASE WHEN CAST(currentR AS float) >= CAST(currentS AS float) AND CAST(currentR AS float) >= CAST(currentT AS float) THEN CAST(currentR AS float) WHEN CAST(currentS AS float) >= CAST(currentR AS float) AND CAST(currentS AS float) >= CAST(currentT AS float) THEN CAST(currentS AS float) ELSE CAST(currentT AS float) END - (CAST(currentR AS float) + CAST(currentS AS float) + CAST(currentT AS float)) / 3.0) / NULLIF((CAST(currentR AS float) + CAST(currentS AS float) + CAST(currentT AS float)) / 3.0, 0) * 100.0) AS avg_current_imbalance_rate,
    COUNT(*) AS event_count
INTO [poweroutput_1d]
FROM [powerinput] TIMESTAMP BY CAST(SUBSTRING(CAST(localtime AS nvarchar(max)), 1, 4) + '-' + SUBSTRING(CAST(localtime AS nvarchar(max)), 5, 2) + '-' + SUBSTRING(CAST(localtime AS nvarchar(max)), 7, 2) + ' ' + SUBSTRING(CAST(localtime AS nvarchar(max)), 9, 2) + ':' + SUBSTRING(CAST(localtime AS nvarchar(max)), 11, 2) + ':' + SUBSTRING(CAST(localtime AS nvarchar(max)), 13, 2) AS datetime)
GROUP BY module, TumblingWindow(day, 1);
