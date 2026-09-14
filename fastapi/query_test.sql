WITH PrepPowerInput AS (
    SELECT
        module,
        event_time,
        localtime,
        localtime_datetime,
        CAST(voltageR AS float) AS v_r,
        CAST(voltageS AS float) AS v_s,
        CAST(voltageT AS float) AS v_t,
        CAST(currentR AS float) AS c_r,
        CAST(currentS AS float) AS c_s,
        CAST(currentT AS float) AS c_t,
        (CAST(voltageR AS float) + CAST(voltageS AS float) + CAST(voltageT AS float)) / 3.0 AS v_avg,
        (CAST(currentR AS float) + CAST(currentS AS float) + CAST(currentT AS float)) / 3.0 AS c_avg,
        CASE WHEN CAST(voltageR AS float) >= CAST(voltageS AS float) AND CAST(voltageR AS float) >= CAST(voltageT AS float) THEN CAST(voltageR AS float) WHEN CAST(voltageS AS float) >= CAST(voltageR AS float) AND CAST(voltageS AS float) >= CAST(voltageT AS float) THEN CAST(voltageS AS float) ELSE CAST(voltageT AS float) END AS v_max,
        CASE WHEN CAST(currentR AS float) >= CAST(currentS AS float) AND CAST(currentR AS float) >= CAST(currentT AS float) THEN CAST(currentR AS float) WHEN CAST(currentS AS float) >= CAST(currentR AS float) AND CAST(currentS AS float) >= CAST(currentT AS float) THEN CAST(currentS AS float) ELSE CAST(currentT AS float) END AS c_max,
        (CAST(powerFactorR AS float) + CAST(powerFactorS AS float) + CAST(powerFactorT AS float)) / 3.0 AS pf_avg,
        CAST(activePower AS float) AS active_power,
        CAST(accumActiveEnergy AS float) AS active_energy
    FROM [powerinput] TIMESTAMP BY localtime_datetime
),

Aggregated1m AS (
    SELECT
        module AS equipment_id,
        CAST(System.Timestamp() AS datetime) AS window_end_time,
        CASE
            WHEN (MIN(CAST(voltageRS AS float)) <= 360.0) OR (MIN(CAST(voltageST AS float)) <= 360.0) OR (MIN(CAST(voltageTR AS float)) <= 360.0) THEN 1
            WHEN ((AVG(CAST(powerFactorR AS float)) + AVG(CAST(powerFactorS AS float)) + AVG(CAST(powerFactorT AS float))) / 3.0) <= 90.0 THEN 1
            ELSE 0
        END AS is_anomaly,
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
    FROM [powerinput] TIMESTAMP BY localtime_datetime
    GROUP BY module, TumblingWindow(minute, 1)
),

Aggregated15m AS (
    SELECT
        module AS equipment_id,
        CAST(System.Timestamp() AS datetime) AS window_end_time,
        AVG(v_r) AS avg_voltage_r,
        AVG(v_s) AS avg_voltage_s,
        AVG(v_t) AS avg_voltage_t,
        AVG(c_r) AS avg_current_r,
        AVG(c_s) AS avg_current_s,
        AVG(c_t) AS avg_current_t,
        AVG(pf_avg) AS avg_power_factor,
        AVG((v_max - v_avg) / NULLIF(v_avg, 0) * 100.0) AS avg_voltage_imbalance_rate,
        AVG((c_max - c_avg) / NULLIF(c_avg, 0) * 100.0) AS avg_current_imbalance_rate,
        MAX(active_power) / 1000.0 AS max_activePower,
        AVG(active_power) / 1000.0 AS avg_activePower,
        MAX(active_energy) - MIN(active_energy) AS [15m_Total_kWh],
        COUNT(*) AS event_count 
    FROM PrepPowerInput
    GROUP BY module, TumblingWindow(minute, 15)
),

ModelInput AS (
    SELECT
        equipment_id,
        window_end_time,
        '15m' AS aggregation_level,
        avg_voltage_r, avg_voltage_s, avg_voltage_t,
        avg_current_r, avg_current_s, avg_current_t,
        avg_power_factor,
        avg_voltage_imbalance_rate, avg_current_imbalance_rate,
        event_count,
        max_activePower AS rolling_15m_peak_kW,
        ([15m_Total_kWh] * 0.466) AS carbon_emission_kg,
        avg_voltage_imbalance_rate AS kepco_10m_v_imb,
        avg_current_imbalance_rate AS kepco_10m_c_imb,
        avg_power_factor AS kepco_30m_pf,
        DATEPART(hour, window_end_time) AS [hour],
        (DATEPART(weekday, window_end_time) + 5) % 7 AS dayofweek,
        CASE WHEN DATEPART(weekday, window_end_time) IN (1, 7) THEN 1 ELSE 0 END AS is_weekend
    FROM Aggregated15m
)

SELECT * 
INTO [poweroutput] 
FROM Aggregated1m;

SELECT
    equipment_id,
    window_end_time,
    avg_voltage_r, avg_voltage_s, avg_voltage_t,
    avg_current_r, avg_current_s, avg_current_t,
    avg_power_factor,
    avg_voltage_imbalance_rate, avg_current_imbalance_rate,
    max_activePower,
    avg_activePower,
    [15m_Total_kWh],
    event_count
INTO [poweroutput_15m]
FROM Aggregated15m;

SELECT *
INTO [aggregated-power-data]
FROM ModelInput;