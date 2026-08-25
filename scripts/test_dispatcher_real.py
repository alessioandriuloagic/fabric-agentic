#!/usr/bin/env python3
"""
Real-world dispatcher backend test.
Tests both Azure DevOps and GitHub Issues with actual credentials (dry-run mode).
"""

__test__ = False

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dev_dispatcher import DispatcherConfig, run_once, DispatcherError, create_tracker, acquire_ado_token


def test_azure_devops_real() -> bool:
    """Test dispatcher with real Azure DevOps configuration (dry-run)."""
    print("\n" + "=" * 60)
    print("AZURE DEVOPS REAL-WORLD TEST (dry-run)")
    print("=" * 60)
    
    try:
        # Load actual dispatcher config
        config_path = Path(__file__).parent.parent / "configuration" / "dispatcher.json"
        
        if not config_path.exists():
            print(f"✗ Config file not found: {config_path}")
            return False
        
        with open(config_path, "r") as f:
            config_dict = json.load(f)
        
        # Verify required fields are present
        ado_config = config_dict.get("azure_devops", {})
        if not all(key in ado_config for key in ["organization", "project", "tenant_domain"]):
            print("✗ Missing required Azure DevOps config fields")
            return False
        
        print(f"✓ Config loaded from: {config_path}")
        print(f"  Organization: {ado_config['organization']}")
        print(f"  Project: {ado_config['project']}")
        print(f"  Tenant: {ado_config['tenant_domain']}")
        
        # Create dispatcher config
        config = DispatcherConfig(
            organization=ado_config["organization"],
            project=ado_config["project"],
            tenant_domain=ado_config["tenant_domain"],
            ado_app_id=ado_config.get("app_id", ""),
            certificate_thumbprint=ado_config.get("certificate_thumbprint", ""),
            dev_agent_display_name=ado_config.get("dev_agent_display_name", "[dev-agent]"),
            github_owner=config_dict.get("github", {}).get("owner", ""),
            github_repository=config_dict.get("github", {}).get("repository", ""),
            github_app_id=int(config_dict.get("github", {}).get("app_id", 0)),
            github_installation_id=int(config_dict.get("github", {}).get("installation_id", 0)),
                github_private_key_path=Path.home() / ".fabric-agentic" / "dev-agent" / "github-app-private-key.pem",
            repository_path=Path(config_dict.get("agent", {}).get("repository_path", ".")),
            claude_command=config_dict.get("agent", {}).get("claude_command", "claude"),
            poll_seconds=int(config_dict.get("agent", {}).get("poll_seconds", 30)),
            tracker_type="azure_devops",
        )
        
        print(f"✓ DispatcherConfig created with tracker_type={config.tracker_type}")
        
        # Try to instantiate tracker (will fail on auth, but tests factory)
        try:
            ado_token_provider = lambda: acquire_ado_token(config)
            tracker = create_tracker(config, ado_token_provider)
            print(f"✓ Tracker created: {tracker.__class__.__name__}")
        except DispatcherError as e:
            print(f"⚠ Tracker creation expected to fail (auth): {e}")
        except Exception as e:
            error_msg = str(e).lower()
            if "token" in error_msg or "certificate" in error_msg or "connect-azaccount" in error_msg:
                print(f"⚠ Tracker creation expected to fail (auth): {e}")
            else:
                print(f"✗ Unexpected error during tracker creation: {e}")
                return False
        
        # Try run_once in dry-run mode
        try:
            with TemporaryDirectory() as tmpdir:
                state_path = Path(tmpdir) / "state.json"
                task_dir = Path(tmpdir) / "tasks"
                
                tasks = run_once(config, state_path, task_dir, dry_run=True)
                print(f"✓ Dry-run completed: {len(tasks)} tasks found")
                for task in tasks:
                    print(f"  - Task: {task}")
                
        except DispatcherError as e:
            error_msg = str(e).lower()
            if "token" in error_msg or "certificate" in error_msg or "azure" in error_msg:
                print(f"✗ Azure DevOps unavailable: {e}")
                return False
            else:
                print(f"✗ Unexpected dispatcher error: {e}")
                return False
        except Exception as e:
            error_msg = str(e).lower()
            if "token" in error_msg or "certificate" in error_msg or "connect-azaccount" in error_msg or "powershell" in error_msg:
                print(f"✗ Azure DevOps unavailable: {e}")
                return False
            else:
                print(f"✗ Unexpected error: {e}")
                return False
        
        print("✓ Azure DevOps backend test PASSED")
        return True
        
    except Exception as e:
        print(f"✗ Azure DevOps test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_github_real() -> bool:
    """Test dispatcher with real GitHub configuration (dry-run)."""
    print("\n" + "=" * 60)
    print("GITHUB ISSUES REAL-WORLD TEST (dry-run)")
    print("=" * 60)
    
    try:
        # Load actual dispatcher config
        config_path = Path(__file__).parent.parent / "configuration" / "dispatcher.json"
        
        if not config_path.exists():
            print(f"✗ Config file not found: {config_path}")
            return False
        
        with open(config_path, "r") as f:
            config_dict = json.load(f)
        
        # Verify required fields are present
        gh_config = config_dict.get("github", {})
        if not all(key in gh_config for key in ["owner", "repository", "app_id", "installation_id"]):
            print("✗ Missing required GitHub config fields")
            return False
        
        print(f"✓ Config loaded from: {config_path}")
        print(f"  Owner: {gh_config['owner']}")
        print(f"  Repository: {gh_config['repository']}")
        print(f"  App ID: {gh_config['app_id']}")
        print(f"  Installation ID: {gh_config['installation_id']}")
        
        # Check if PEM file exists
        configured_pem_path = Path(gh_config.get("private_key_path", "/fake/path.pem"))
        pem_path = configured_pem_path
        if not pem_path.exists():
            pem_path = Path.home() / ".fabric-agentic" / "dev-agent" / "github-app-private-key.pem"
        pem_exists = pem_path.exists()
        print(f"  PEM Key Path: {pem_path} (exists: {pem_exists})")
        
        # Create dispatcher config
        config = DispatcherConfig(
            organization=config_dict.get("azure_devops", {}).get("organization", ""),
            project=config_dict.get("azure_devops", {}).get("project", ""),
            tenant_domain=config_dict.get("azure_devops", {}).get("tenant_domain", ""),
            ado_app_id=config_dict.get("azure_devops", {}).get("app_id", ""),
            certificate_thumbprint=config_dict.get("azure_devops", {}).get("certificate_thumbprint", ""),
            dev_agent_display_name=config_dict.get("azure_devops", {}).get("dev_agent_display_name", "[dev-agent]"),
            github_owner=gh_config["owner"],
            github_repository=gh_config["repository"],
            github_app_id=int(gh_config["app_id"]),
            github_installation_id=int(gh_config["installation_id"]),
            github_private_key_path=pem_path,
            repository_path=Path(config_dict.get("agent", {}).get("repository_path", ".")),
            claude_command=config_dict.get("agent", {}).get("claude_command", "claude"),
            poll_seconds=int(config_dict.get("agent", {}).get("poll_seconds", 30)),
            tracker_type="github_issues",
        )
        
        print(f"✓ DispatcherConfig created with tracker_type={config.tracker_type}")
        
        # Try to instantiate tracker (will fail on auth, but tests factory)
        try:
            ado_token_provider = lambda: acquire_ado_token(config)
            tracker = create_tracker(config, ado_token_provider)
            print(f"✓ Tracker created: {tracker.__class__.__name__}")
        except DispatcherError as e:
            print(f"⚠ Tracker creation expected to fail (auth): {e}")
        except FileNotFoundError as e:
            if "pem" in str(e).lower() or "private_key" in str(e).lower():
                print(f"⚠ Tracker creation expected to fail (missing PEM): {e}")
            else:
                print(f"✗ Unexpected FileNotFoundError: {e}")
                return False
        except Exception as e:
            error_msg = str(e).lower()
            if "pem" in error_msg or "private_key" in error_msg or "token" in error_msg:
                print(f"⚠ Tracker creation expected to fail (auth): {e}")
            else:
                print(f"✗ Unexpected error during tracker creation: {e}")
                return False
        
        # Try run_once in dry-run mode
        try:
            with TemporaryDirectory() as tmpdir:
                state_path = Path(tmpdir) / "state.json"
                task_dir = Path(tmpdir) / "tasks"
                
                tasks = run_once(config, state_path, task_dir, dry_run=True)
                print(f"✓ Dry-run completed: {len(tasks)} tasks found")
                for task in tasks:
                    print(f"  - Task: {task}")
                
        except DispatcherError as e:
            error_msg = str(e).lower()
            if "pem" in error_msg or "private_key" in error_msg or "token" in error_msg or "github" in error_msg:
                print(f"✗ GitHub Issues unavailable: {e}")
                return False
            else:
                print(f"✗ Unexpected dispatcher error: {e}")
                return False
        except FileNotFoundError as e:
            if "pem" in str(e).lower() or "private_key" in str(e).lower():
                print(f"✗ GitHub PEM unavailable: {e}")
                return False
            else:
                print(f"✗ Unexpected FileNotFoundError: {e}")
                return False
        except Exception as e:
            error_msg = str(e).lower()
            if "pem" in error_msg or "private_key" in error_msg or "token" in error_msg or "github" in error_msg:
                print(f"✗ GitHub Issues unavailable: {e}")
                return False
            else:
                print(f"✗ Unexpected error: {e}")
                return False
        
        print("✓ GitHub Issues backend test PASSED")
        return True
        
    except Exception as e:
        print(f"✗ GitHub test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run both real-world backend tests."""
    print("\n" + "=" * 60)
    print("DISPATCHER REAL-WORLD BACKENDS TEST")
    print("=" * 60)
    
    azure_result = test_azure_devops_real()
    github_result = test_github_real()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Azure DevOps: {'✓ PASS' if azure_result else '✗ FAIL'}")
    print(f"GitHub Issues: {'✓ PASS' if github_result else '✗ FAIL'}")
    
    if azure_result and github_result:
        print("\n✓ All real-world backend tests PASSED")
        return 0
    else:
        print("\n✗ Some real-world backend tests FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
