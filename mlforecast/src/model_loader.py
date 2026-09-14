# src/model_loader.py

from neuralforecast import NeuralForecast


def load_neuralforecast_model(model_dir: str) -> NeuralForecast:
    model = NeuralForecast.load(path=model_dir)
    return model


def load_models(nhits_dir: str, tft_dir: str) -> dict:
    return {
        "NHITS": load_neuralforecast_model(nhits_dir),
        "TFT": load_neuralforecast_model(tft_dir),
    }