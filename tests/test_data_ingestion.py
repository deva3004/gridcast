from src.ingestion.data_ingestion import load_config


def test_load_config_reads_real_config_file():
    config = load_config()

    assert config.base_url == "https://api.eia.gov/v2/electricity/rto/region-data/data/"
    assert config.regions == ("PJM", "CISO", "ERCO")
    assert config.series_types == ("D", "DF")
    assert config.page_size == 5000
    assert config.retry.max_attempts == 5
    assert 429 in config.retry.status_forcelist
