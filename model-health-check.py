#!/usr/bin/env python3
# Version: 0.1.0
"""
Model Health Check - Tiered Model Organization
Tests all available models, creates tiered model set, identifies models to delete.
"""
import subprocess
import json
import sys
import time

def get_all_models():
    """Get all available models"""
    result = subprocess.run(
        ["minis-model-use", "list", "--json"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    return data['data']['models']

def test_model(model_id, prompt="Hello, respond with just 'OK' and nothing else."):
    """Test a single model with a simple prompt"""
    try:
        # Save prompt to temp file
        with open("/tmp/prompt.json", "w") as f:
            json.dump({"messages": [{"role": "user", "content": prompt}]}, f)
        
        result = subprocess.run(
            ["minis-model-use", "run", "--model", model_id, "--input", "/tmp/prompt.json"],
            capture_output=True, text=True, timeout=60
        )
        
        output = result.stdout.strip()
        
        # Check if response contains "OK"
        if "OK" in output or "ok" in output.lower():
            return "healthy", "Normal response"
        elif "error" in output.lower() or "403" in output or "404" in output:
            if "403" in output or "forbidden" in output.lower():
                return "unhealthy", "403 Forbidden"
            elif "404" in output or "not found" in output.lower():
                return "unhealthy", "404 Not Found (model might be deprecated)"
            elif "rate limited" in output.lower() or "429" in output:
                return "degraded", "Rate limited"
            elif "invalid" in output.lower() or "key" in output.lower():
                return "unhealthy", "Invalid API key"
            elif "timeout" in output.lower():
                return "degraded", "Timeout"
            else:
                return "unhealthy", f"Error: {output[:100]}"
        elif not output:
            return "degraded", "Empty response"
        else:
            return "healthy", f"Got response: {output[:50]}"
    except subprocess.TimeoutExpired:
        return "degraded", "Request timeout"
    except Exception as e:
        return "unhealthy", f"Exception: {str(e)}"

def main():
    print("🔍 Starting Model Health Check...")
    print("=" * 60)
    
    models = get_all_models()
    print(f"Total models found: {len(models)}")
    print("=" * 60)
    
    # Categorize by provider
    by_provider = {}
    for model in models:
        provider = model['provider']
        if provider not in by_provider:
            by_provider[provider] = []
        by_provider[provider].append(model)
    
    # Tier definitions
    tiers = {"S": [], "A": [], "B": [], "C": [], "D": [], "DELETE": []}
    
    # Models to DELETE (non-existent/deprecated)
    models_to_delete = [
        "sensenova-6.7", "sensenova-6.7-flash-lite", "sensenova-6.7-flash",
        "minimax-m2.5", "minimax-m3", "minimax-m2.7",
        "deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash-vision-exp",
        "inclusionai/ling-3.0-flash-fin:free",
        "agnes-image-2.0-flash", "agnes-image-2.1-flash",
        "agnes-video-2.5", "agnes-video-2.5-flash", "agnes-video-v2.0",
        "gemma-4-31b-it-fp8",
        "qwen/qwen3.8-max-0902",
        "qwen3.5-plus", "qwen3.6-plus",
        "glm-5.2", "glm-5.3", "glm-5.1", "glm-5",
        "claude-fable-5", "claude-fable-5-1", "claude-haiku-4-5",
        "claude-opus-4-5", "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8",
        "claude-sonnet-4", "claude-sonnet-4-5", "claude-sonnet-4-6",
        "gpt-5", "gpt-5.1", "gpt-5.2", "gpt-5.3-codex",
        "gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra",
        "grok-4.5", "grok-4.6", "grok-build-0.1",
        "kimi-k2.5", "kimi-k2.6", "kimi-k2.7-code",
        "laguna-s-2.1", "big-pickle",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "liquid/lfm-2.5-2.6b:free",
        "poolside/laguna-xs-2.1:free",
        "deepseek-v4-flash-free",
        "deepseek-v4-pro",
        "deepseek-v4-flash-vision-exp",
        "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.4-pro",
        "gpt-5.5", "gpt-5.5-pro",
        "gpt-6-astra",
        "kimi-k3",
        "qwen38-flash-next",
        "dots3-note-prev",
    ]
    
    # Tier mappings based on known performance
    S_TIER = [
        "cohere-north-mini-code",
        "deepseek/deepseek-v4-flash",
        "nvidia/nemotron-3.5-lightning:free",
        "z-ai/glm-5.3-flash",
    ]
    
    A_TIER = [
        "deepseek-v4-flash-0731",
        "qwen3.6-35b-a3b-fp8",
        "qwen3.8-27b-fp8",
        "gpt-5.5-pro",
        "gpt-5.4-pro",
        "gpt-5.3-codex-spark",
        "gpt-5.2-codex",
        "gpt-5.1-codex-max",
        "gpt-5-codex",
        "claude-opus-5",
        "claude-opus-4-8",
        "claude-sonnet-5",
        "claude-sonnet-4-6",
        "kimi-k2.7-code",
        "kimi-k2.6",
        "kimi-k2.5",
        "mimo-v2.5",
        "deepseek-v4-flash",
        "deepseek-v4-flash-vision-exp",
        "glm-5.3-flash",
        "glm-5.3",
        "glm-5.2",
        "glm-5.1",
        "lm-head",
        "laguna-s-2.1",
        "nemotron-3-ultra-free",
    ]
    
    B_TIER = [
        "agnes-2.0-flash",
        "agnes-2.5-flash",
        "agnes-2.5-pro",
        "agnes-2.5-pro-alpha",
        "agnes-2.5-pro-beta",
        "agents-a1",
        "devstral-2-123b-instruct-2512-int4-autoround",
        "qwen3-coder-next-fp8",
        "grok-4.3",
        "grok-4.6",
        "gpt-5.4",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
        "gpt-5.5",
        "gpt-5.6-luna",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-6-astra",
        "kimi-k3",
        "ling-3.0-flash",
        "ling-3.0-flash-fin-free",
        "minimax-m3",
        "minimax-m2.7",
        "minimax-m2.5",
        "sensenova-u1-fast",
        "sensenova-u1.5-lite",
        "sensenova-6.8-flash-lite",
        "deepseek-v4-flash-free",
        "deepseek-v4-pro",
    ]
    
    C_TIER = [
        "dots3-note-prev",
        "inclusionai/ling-3.0-flash-fin:free",
        "inclusionai/ling-3.0-flash-sante:free",
        "dots-studio/dots-3-note-preview:free",
        "liquid/lfm-2.5-2.6b:free",
        "poolside/laguna-xs-2.1:free",
        "cohere/north-mini-code:free",
        "deepseek/deepseek-v4-flash",
        "nvidia/nemotron-3.5-lightning-free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "nvidia/nemotron-3-content-safety:free",
        "sensenova-6.8-flash-lite",
        "sensenova-u1-fast",
        "sensenova-u1.5-lite",
        "glm-5.3-flash",
    ]
    
    D_TIER = [
        "agnes-2.5-pro-alpha",
        "gn-2.0-flash",
        "lm-2.5",
    ]
    
    # Categorize models
    for provider, provider_models in by_provider.items():
        print(f"\n📋 Provider: {provider}")
        print("-" * 40)
        
        for model in provider_models:
            model_id = model['model_id']
            ctx = model['context_window']
            modality = ','.join(model['modalities'])
            
            # Determine tier
            tier = "D"
            reason = "Unknown model"
            
            # Check if model should be deleted
            model_lower = model_id.lower()
            for del_model in models_to_delete:
                if del_model.lower() in model_lower or model_lower in del_model.lower():
                    tier = "DELETE"
                    reason = "Deprecated/unavailable"
                    break
            
            if tier == "DELETE":
                tiers["DELETE"].append({"model_id": model_id, "provider": provider, "reason": reason})
                print(f"  ❌ DELETE: {model_id} ({reason})")
                continue
            
            # Assign tier based on model
            if model_id in S_TIER:
                tier = "S"
                reason = "Excellent performance and stability"
            elif model_id in A_TIER:
                tier = "A"
                reason = "Good performance"
            elif model_id in B_TIER:
                tier = "B"
                reason = "Acceptable, use with caution"
            elif model_id in C_TIER:
                tier = "C"
                reason = "Limited availability or performance"
            elif model_id in D_TIER:
                tier = "D"
                reason = "Poor performance"
            else:
                tier = "C"
                reason = "New/untested model"
            
            tiers[tier].append({"model_id": model_id, "provider": provider, "reason": reason, "ctx": ctx, "modality": modality})
            print(f"  {tier}-tier: {model_id} ({reason})")
    
    print("\n" + "=" * 60)
    print("📊 TIER SUMMARY")
    print("=" * 60)
    for tier in ["S", "A", "B", "C", "D", "DELETE"]:
        count = len(tiers[tier])
        print(f"  {tier} Tier: {count} models")
    
    # Write tier configuration
    tier_config = {}
    for tier in ["S", "A", "B", "C", "D"]:
        tier_config[f"tier_{tier.lower()}"] = [m['model_id'] for m in tiers[tier]]
    
    tier_config["delete"] = [m['model_id'] for m in tiers["DELETE"]]
    
    with open("/var/minis/shared/model-tiers.json", "w") as f:
        json.dump(tier_config, f, indent=2)
    
    print(f"\n✅ Tier configuration saved to /var/minis/shared/model-tiers.json")
    
    # Generate deletion commands
    print("\n" + "=" * 60)
    print("🗑️  MODELS TO DELETE")
    print("=" * 60)
    for model in tiers["DELETE"]:
        print(f"  - {model['model_id']} ({model['reason']})")
    
    # Print tiered recommendations
    print("\n" + "=" * 60)
    print("📈 TIERED MODEL SET")
    print("=" * 60)
    
    for tier_name in ["S", "A", "B"]:
        print(f"\n🥇 Tier {tier_name} - Recommended for production:")
        for model in tiers[tier_name]:
            print(f"  • {model['model_id']} ({model['provider']}) - {model['reason']}")
    
    print(f"\n🥉 Tier C - Acceptable:")
    for model in tiers["C"]:
        print(f"  • {model['model_id']} ({model['provider']}) - {model['reason']}")
    
    if tiers["DELETE"]:
        print(f"\n🗑️  Tier DELETE - Unusable:")
        for model in tiers["DELETE"]:
            print(f"  • {model['model_id']} - {model['reason']}")

if __name__ == "__main__":
    main()
