import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def download():
    print("⏳ Pre-downloading embedding model for production...")
    try:
        from sentence_transformers import SentenceTransformer
        # This will download the model to the default cache directory (e.g. ~/.cache/huggingface)
        model = SentenceTransformer('all-mpnet-base-v2')
        print(f"✅ Model 'all-mpnet-base-v2' successfully cached.")
    except Exception as e:
        print(f"❌ Failed to download model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    download()
