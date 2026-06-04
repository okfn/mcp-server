from unittest.mock import patch, MagicMock, Mock
from mcp_server.server import load_python_plugins


class TestPythonPlugins:
    def test_loads_only_plugins_with_mcp_server_group_entrypoints(self):
        mcp_mock = MagicMock()

        # A plugin with "mcp_server" entry point that should be loaded
        mock_plugin_register_tools = MagicMock()
        mock_plugin_entry_point = Mock()
        mock_plugin_entry_point.module = "mcp_server_test"
        mock_plugin_entry_point.group = "mcp_server"
        mock_plugin_entry_point.load.return_value = mock_plugin_register_tools

        # A plugin without "mcp_server" entry point that shouldn't be loaded
        mock_non_mcp_server_register_tools = MagicMock()
        mock_non_mcp_plugin_entry_point = Mock()
        mock_non_mcp_plugin_entry_point.module = "plugin2"
        mock_non_mcp_plugin_entry_point.group = "another_group"
        mock_non_mcp_plugin_entry_point.load.return_value = mock_non_mcp_server_register_tools

        # A plugin without group that shouldn't be loaded
        mock_non_group_server_register_tools = MagicMock()
        mock_non_mcp_plugin_entry_point = Mock()
        mock_non_mcp_plugin_entry_point.module = "plugin3"
        mock_non_mcp_plugin_entry_point.load.return_value = mock_non_group_server_register_tools

        with patch("mcp_server.server.importlib.metadata.entry_points") as mock_eps:
            # mock_eps is the list of entrypoints in the virtualenv.
            mock_eps.return_value = [mock_plugin_entry_point, mock_non_mcp_plugin_entry_point, mock_non_mcp_plugin_entry_point]

            load_python_plugins(mcp_mock)

            # The plugin must be handed a namespaced sub-registry, not the root
            # registry, so its tool names get prefixed by package and cannot
            # collide with other plugins.
            mcp_mock.for_plugin.assert_called_once_with("mcp_server_test")
            mock_plugin_register_tools.assert_called_once_with(mcp_mock.for_plugin.return_value)
            mock_non_mcp_server_register_tools.assert_not_called()
            mock_non_group_server_register_tools.assert_not_called()
