"""Tests for ConfigManager."""

import pytest
import yaml

from videoapi.core.config_manager import ConfigManager


class TestConfigManager:
    """Test cases for ConfigManager."""

    def test_init_with_valid_config(self, temp_dir, sample_config):
        """Test initialization with valid configuration file."""
        config_file = temp_dir / "test_config.yaml"

        with open(config_file, "w") as f:
            yaml.dump(sample_config, f)

        config_manager = ConfigManager(str(config_file))

        assert config_manager.get("video.width") == 640
        assert config_manager.get("video.height") == 480
        assert config_manager.get("recording.enable_deduplication") is True

    def test_init_with_nonexistent_file(self):
        """Test initialization with non-existent configuration file."""
        config_manager = ConfigManager("nonexistent.yaml")

        # Should fall back to default config
        assert config_manager.get("video.width") == 640
        assert config_manager.get("video.height") == 360  # Default value

    def test_init_with_invalid_yaml(self, temp_dir):
        """Test initialization with invalid YAML file."""
        config_file = temp_dir / "invalid.yaml"

        with open(config_file, "w") as f:
            f.write("invalid: yaml: content: [")

        with pytest.raises(ValueError, match="Invalid YAML configuration"):
            ConfigManager(str(config_file))

    def test_get_with_dot_notation(self, config_manager):
        """Test getting values using dot notation."""
        assert config_manager.get("video.width") == 640
        assert config_manager.get("recording.fourcc_codec") == "mp4v"
        assert config_manager.get("nonexistent.key", "default") == "default"

    def test_set_with_dot_notation(self, config_manager):
        """Test setting values using dot notation."""
        config_manager.set("video.width", 1920)
        config_manager.set("new.nested.key", "value")

        assert config_manager.get("video.width") == 1920
        assert config_manager.get("new.nested.key") == "value"

    def test_validate_valid_config(self, config_manager):
        """Test validation with valid configuration."""
        assert config_manager.validate() is True

    def test_validate_invalid_width(self, config_manager):
        """Test validation with invalid width."""
        config_manager.set("video.width", -1)
        assert config_manager.validate() is False

    def test_validate_invalid_duration(self, config_manager):
        """Test validation with invalid duration."""
        config_manager.set("recording.duration_seconds", -5)
        assert config_manager.validate() is False

    def test_save_config(self, config_manager, temp_dir):
        """Test saving configuration to file."""
        save_path = temp_dir / "saved_config.yaml"

        config_manager.set("video.width", 1280)
        config_manager.save(str(save_path))

        # Load saved config and verify
        with open(save_path, "r") as f:
            saved_config = yaml.safe_load(f)

        assert saved_config["video"]["width"] == 1280

    def test_reload_config(self, temp_dir, sample_config):
        """Test reloading configuration from file."""
        config_file = temp_dir / "reload_test.yaml"

        # Create initial config
        with open(config_file, "w") as f:
            yaml.dump(sample_config, f)

        config_manager = ConfigManager(str(config_file))
        assert config_manager.get("video.width") == 640

        # Modify file
        sample_config["video"]["width"] = 1920
        with open(config_file, "w") as f:
            yaml.dump(sample_config, f)

        # Reload and verify
        config_manager.reload()
        assert config_manager.get("video.width") == 1920
