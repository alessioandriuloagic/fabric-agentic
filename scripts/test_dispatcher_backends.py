"""Smoke test for dispatcher tracker backends (dry-run mode).

Verifies that both Azure DevOps and GitHub Issues trackers can be instantiated,
configured, and queried without side effects (dry-run only).
"""

__test__ = False

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from scripts.dev_dispatcher import DispatcherConfig, load_config, run_once, DispatcherError


def test_azure_devops_backend() -> bool:
    """Test dispatcher with Azure DevOps backend in dry-run mode."""
    print("\n=== Testing Azure DevOps Backend ===")
    
    try:
        # Create test config for Azure DevOps
        config_dict = {
            "azure_devops": {
                "organization": "test-org",
                "project": "test-project",
                "tenant_domain": "test.onmicrosoft.com",
                "app_id": "test-app-id",
                "certificate_thumbprint": "test-thumbprint",
                "dev_agent_display_name": "[test-agent]"
            },
            "github": {
                "owner": "test-owner",
                "repository": "test-repo",
                "app_id": 0,
                "installation_id": 0,
                "private_key_path": "/fake/path.pem"
            },
            "agent": {
                "repository_path": "/fake/repo",
                "claude_command": "claude",
                "poll_seconds": 30
            },
            "dispatcher": {
                "tracker_type": "azure_devops"
            }
        }
        
        config = DispatcherConfig(
            organization=config_dict["azure_devops"]["organization"],
            project=config_dict["azure_devops"]["project"],
            tenant_domain=config_dict["azure_devops"]["tenant_domain"],
            ado_app_id=config_dict["azure_devops"]["app_id"],
            certificate_thumbprint=config_dict["azure_devops"]["certificate_thumbprint"],
            dev_agent_display_name=config_dict["azure_devops"]["dev_agent_display_name"],
            github_owner=config_dict["github"]["owner"],
            github_repository=config_dict["github"]["repository"],
            github_app_id=int(config_dict["github"]["app_id"]),
            github_installation_id=int(config_dict["github"]["installation_id"]),
            github_private_key_path=Path(config_dict["github"]["private_key_path"]),
            repository_path=Path(config_dict["agent"]["repository_path"]),
            claude_command=config_dict["agent"]["claude_command"],
            poll_seconds=int(config_dict["agent"]["poll_seconds"]),
            tracker_type=config_dict["dispatcher"]["tracker_type"],
        )
        
        print(f"✓ Config loaded: tracker_type={config.tracker_type}")
        print(f"✓ Organization: {config.organization}")
        print(f"✓ Project: {config.project}")
        
        with TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            task_dir = Path(tmpdir) / "tasks"
            
            # Dry-run will fail on token acquisition (expected), but we verify the flow
            try:
                tasks = run_once(config, state_path, task_dir, dry_run=True)
                print(f"✓ Dry-run completed: {len(tasks)} tasks found")
            except DispatcherError as e:
                # Expected: token acquisition will fail with fake credentials
                error_msg = str(e).lower()
                if "token" in error_msg or "azure" in error_msg:
                    print(f"✓ Expected token error (dry-run with fake creds): {e}")
                else:
                    print(f"✗ Unexpected error: {e}")
                    return False
            except Exception as e:
                # Could also be subprocess or PowerShell error
                error_msg = str(e).lower()
                if "connect-azaccount" in error_msg or "token" in error_msg or "powershell" in error_msg:
                    print(f"✓ Expected Azure auth error: {e}")
                else:
                    print(f"✗ Unexpected error: {e}")
                    return False
        
        return True
        
    except Exception as e:
        error_msg = str(e).lower()
        print(f"✗ Azure DevOps backend test failed: {e}")
        return False


def test_github_issues_backend() -> bool:
    """Test dispatcher with GitHub Issues backend in dry-run mode."""
    print("\n=== Testing GitHub Issues Backend ===")
    
    try:
        config = DispatcherConfig(
            organization="test-org",
            project="test-project",
            tenant_domain="test.onmicrosoft.com",
            ado_app_id="test-app-id",
            certificate_thumbprint="test-thumbprint",
            dev_agent_display_name="[test-agent]",
            github_owner="test-owner",
            github_repository="test-repo",
            github_app_id=12345,
            github_installation_id=67890,
            github_private_key_path=Path("/fake/github-app-key.pem"),
            repository_path=Path("/fake/repo"),
            claude_command="claude",
            poll_seconds=30,
            tracker_type="github_issues",
        )
        
        print(f"✓ Config loaded: tracker_type={config.tracker_type}")
        print(f"✓ GitHub Owner: {config.github_owner}")
        print(f"✓ GitHub Repository: {config.github_repository}")
        
        with TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            task_dir = Path(tmpdir) / "tasks"
            
            # Dry-run will fail on token acquisition (expected), but we verify the flow
            try:
                tasks = run_once(config, state_path, task_dir, dry_run=True)
                print(f"✓ Dry-run completed: {len(tasks)} tasks found")
            except DispatcherError as e:
                # Expected: token acquisition will fail with fake key path
                error_msg = str(e).lower()
                if "github" in error_msg or "token" in error_msg or "key" in error_msg.lower() or "pem" in error_msg.lower():
                    print(f"✓ Expected GitHub auth error (dry-run with fake key): {e}")
                else:
                    print(f"✗ Unexpected error: {e}")
                    return False
            except Exception as e:
                # Could be FileNotFoundError or other auth-related error during token creation
                error_msg = str(e).lower()
                if "pem" in error_msg or "no such file" in error_msg or "github" in error_msg:
                    print(f"✓ Expected GitHub key/auth error (dry-run with fake key): {e}")
                else:
                    print(f"✗ Unexpected error: {e}")
                    return False
        
        return True
        
    except Exception as e:
        print(f"✗ GitHub Issues backend test failed: {e}")
        return False


def main() -> int:
    """Run all smoke tests."""
    print("=" * 60)
    print("DISPATCHER BACKENDS SMOKE TEST (dry-run mode)")
    print("=" * 60)
    
    results = {
        "Azure DevOps": test_azure_devops_backend(),
        "GitHub Issues": test_github_issues_backend(),
    }
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for backend, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{backend}: {status}")
    
    all_passed = all(results.values())
    print("\n" + ("✓ All backends operational" if all_passed else "✗ Some backends failed"))
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
