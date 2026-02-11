"""たんぼアドバイザー 設定値"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LINE
    line_channel_secret: str = ""
    line_channel_access_token: str = ""

    # Database
    database_url: str = "sqlite:///./tanbo.db"

    # Amedas
    amedas_base_url: str = "https://www.jma.go.jp/bosai/amedas"
    amedas_fetch_interval_minutes: int = 60
    forecast_url: str = "https://www.jma.go.jp/bosai/forecast/data/forecast"
    hiroshima_area_code: str = "340000"

    # Notifications
    morning_notification_hour: int = 7

    # Blast risk
    blast_risk_threshold_hours: float = 10.0
    blast_moderate_threshold_hours: float = 6.0
    blast_optimal_temp_min: float = 20.0
    blast_optimal_temp_max: float = 28.0
    blast_humidity_threshold: float = 90.0

    # Heat stress
    heat_stress_high_temp: float = 27.0
    heat_stress_moderate_temp: float = 26.0
    heat_stress_eval_days: int = 20
    heat_stress_night_high_temp: float = 23.0  # 夜温（最低気温）高温閾値

    # Water temperature (establishment)
    water_temp_threshold: float = 15.0   # 活着期の水温警戒閾値 (℃)
    establishment_days: int = 10         # 活着期の日数

    # Blast risk (stage-aware)
    blast_humidity_threshold_panicle: float = 85.0  # 幼穂形成期〜出穂期の湿度閾値（通常90→85）

    # Accumulated temperature
    base_temperature: float = 10.0
    elevation_lapse_rate: float = 0.006  # ℃/m

    # Logging
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
