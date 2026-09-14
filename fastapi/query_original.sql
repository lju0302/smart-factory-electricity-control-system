-- =========================================================================
-- 1단계: 원시 데이터에서 형 변환(Casting) 및 상별 최댓값 사전 계산
-- =========================================================================
WITH PrepPowerInput AS (
    SELECT
        module,
        event_time,
        CAST(voltageR AS float) AS v_r,
        CAST(voltageS AS float) AS v_s,
        CAST(voltageT AS float) AS v_t,
        CAST(currentR AS float) AS c_r,
        CAST(currentS AS float) AS c_s,
        CAST(currentT AS float) AS c_t,
        
        (CAST(voltageR AS float) + CAST(voltageS AS float) + CAST(voltageT AS float)) / 3.0 AS v_avg,
        (CAST(currentR AS float) + CAST(currentS AS float) + CAST(currentT AS float)) / 3.0 AS c_avg,
        CASE 
            WHEN CAST(voltageR AS float) >= CAST(voltageS AS float) AND CAST(voltageR AS float) >= CAST(voltageT AS float) THEN CAST(voltageR AS float)
            WHEN CAST(voltageS AS float) >= CAST(voltageR AS float) AND CAST(voltageS AS float) >= CAST(voltageT AS float) THEN CAST(voltageS AS float)
            ELSE CAST(voltageT AS float)
        END AS v_max,
        CASE 
            WHEN CAST(currentR AS float) >= CAST(currentS AS float) AND CAST(currentR AS float) >= CAST(currentT AS float) THEN CAST(currentR AS float)
            WHEN CAST(currentS AS float) >= CAST(currentR AS float) AND CAST(currentS AS float) >= CAST(currentT AS float) THEN CAST(currentS AS float)
            ELSE CAST(currentT AS float)
        END AS c_max,
        (CAST(powerFactorR AS float) + CAST(powerFactorS AS float) + CAST(powerFactorT AS float)) / 3.0 AS pf_avg,
        CAST(activePower AS float) AS active_power,
        CAST(accumActiveEnergy AS float) AS active_energy
    FROM [powerinput]  -- 인풋 소스 일치화 및 괄호 추가 가능
),

-- =========================================================================
-- 2단계: 1분 단위 실시간 집계 데이터셋 정의 (기존 1분 쿼리)
-- =========================================================================
Aggregated1m AS (
    SELECT
        module AS equipment_id,
        CAST(System.Timestamp() AS datetime) AS window_end_time, -- 소괄호() 추가
        CASE
            WHEN (MIN(CAST(voltageRS AS float)) <= 360.0) 
                OR (MIN(CAST(voltageST AS float)) <= 360.0) 
                OR (MIN(CAST(voltageTR AS float)) <= 360.0) 
                THEN 1
            WHEN ((AVG(CAST(powerFactorR AS float)) + AVG(CAST(powerFactorS AS float)) + AVG(CAST(powerFactorT AS float))) / 3.0) <= 90.0 
                THEN 1
            ELSE 0
        END AS is_anomaly,
        AVG(CAST(voltageR AS float)) AS avg_voltage_r,
        AVG(CAST(voltageS AS float)) AS avg_voltage_s,
        AVG(CAST(voltageT AS float)) AS avg_voltage_t,
        AVG(CAST(currentR AS float)) AS avg_current_r,
        AVG(CAST(currentS AS float)) AS avg_current_s,
        AVG(CAST(currentT AS float)) AS avg_current_t,
        AVG((CAST(powerFactorR AS float) + CAST(powerFactorS AS float) + CAST(powerFactorT AS float)) / 3.0) AS avg_power_factor,
        -- 복잡한 불평형률 수식
        AVG((CASE WHEN CAST(voltageR AS float) >= CAST(voltageS AS float) AND CAST(voltageR AS float) >= CAST(voltageT AS float) THEN CAST(voltageR AS float) WHEN CAST(voltageS AS float) >= CAST(voltageR AS float) AND CAST(voltageS AS float) >= CAST(voltageT AS float) THEN CAST(voltageS AS float) ELSE CAST(voltageT AS float) END - (CAST(voltageR AS float) + CAST(voltageS AS float) + CAST(voltageT AS float)) / 3.0) / NULLIF((CAST(voltageR AS float) + CAST(voltageS AS float) + CAST(voltageT AS float)) / 3.0, 0) * 100.0) AS avg_voltage_imbalance_rate,
        AVG((CASE WHEN CAST(currentR AS float) >= CAST(currentS AS float) AND CAST(currentR AS float) >= CAST(currentT AS float) THEN CAST(currentR AS float) WHEN CAST(currentS AS float) >= CAST(currentR AS float) AND CAST(currentS AS float) >= CAST(currentT AS float) THEN CAST(currentS AS float) ELSE CAST(currentT AS float) END - (CAST(currentR AS float) + CAST(currentS AS float) + CAST(currentT AS float)) / 3.0) / NULLIF((CAST(currentR AS float) + CAST(currentS AS float) + CAST(currentT AS float)) / 3.0, 0) * 100.0) AS avg_current_imbalance_rate,
        COUNT(*) AS event_count
    FROM [powerinput]
    GROUP BY module, TumblingWindow(minute, 1)
),

-- =========================================================================
-- 3단계: 15분 단위 공통 집계 데이터셋 생성 (1회만 집계 연산 수행)
-- =========================================================================
Aggregated15m AS (
    SELECT
        module AS equipment_id,
        CAST(System.Timestamp() AS datetime) AS window_end_time, -- 소괄호() 추가
        AVG(v_r) AS avg_voltage_r,
        AVG(v_s) AS avg_voltage_s,
        AVG(v_t) AS avg_voltage_t,
        AVG(c_r) AS avg_current_r,
        AVG(c_s) AS avg_current_s,
        AVG(c_t) AS avg_current_t,
        AVG(pf_avg) AS avg_power_factor,
        
        -- 전압/전류 불평형률 계산 (1단계에서 계산된 v_max, v_avg 참조)
        AVG((v_max - v_avg) / NULLIF(v_avg, 0) * 100.0) AS avg_voltage_imbalance_rate,
        AVG((c_max - c_avg) / NULLIF(c_avg, 0) * 100.0) AS avg_current_imbalance_rate,
        
        -- 유효전력 관련 파생 피처
        MAX(active_power) / 1000.0 AS max_activePower,
        AVG(active_power) / 1000.0 AS avg_activePower,
        MAX(active_energy) - MIN(active_energy) AS [15m_Total_kWh],
        COUNT(*) AS event_count 
    FROM PrepPowerInput
    GROUP BY module, TumblingWindow(minute, 2) --잠시수정
),

-- =========================================================================
-- 4단계: 집계된 결과에서 ML API 연동용 데이터 구조(ModelInput) 생성
-- =========================================================================
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
        
        -- KEPCO 규격을 해당 윈도우 계산값으로 매칭
        avg_voltage_imbalance_rate AS kepco_10m_v_imb,
        avg_current_imbalance_rate AS kepco_10m_c_imb,
        avg_power_factor AS kepco_30m_pf,
        
        -- 시간 변수
        DATEPART(hour, window_end_time) AS [hour],
        (DATEPART(weekday, window_end_time) + 5) % 7 AS dayofweek,
        CASE WHEN DATEPART(weekday, window_end_time) IN (1, 7) THEN 1 ELSE 0 END AS is_weekend
    FROM Aggregated15m
)

-- =========================================================================
-- [출력 1]: 1분 단위 임계점 및 역률 이상 유무 판단 결과 저장 (poweroutput)
-- =========================================================================
SELECT * 
INTO [poweroutput] 
FROM Aggregated1m;

-- =========================================================================
-- [출력 2]: 15분 기본 집계 데이터 저장 (poweroutput_15m)
-- =========================================================================
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

-- =========================================================================
-- [출력 3]: Event Hub로 집계 데이터를 전송하여 Azure Functions 실행 유도
-- =========================================================================
SELECT *
INTO [aggregated-power-data]
FROM ModelInput;