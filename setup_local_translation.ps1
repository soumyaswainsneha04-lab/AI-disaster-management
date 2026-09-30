$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==============================================="
Write-Host " Disaster AI India - FREE Local Translation"
Write-Host "==============================================="
Write-Host ""
Write-Host "Installing local translation packages..."
Write-Host "No API key or paid service is required."
Write-Host ""

python -m pip install --upgrade pip
python -m pip install torch transformers sentencepiece

Write-Host ""
Write-Host "Packages installed successfully."
Write-Host ""
Write-Host "The first translation will download:"
Write-Host "facebook/nllb-200-distilled-600M (~2.5 GB)."
Write-Host "It is a free local model; no subscription or API key is needed."
Write-Host ""
Write-Host "Pre-downloading the model now..."
Write-Host ""

python -c "from transformers import AutoTokenizer, AutoModelForSeq2SeqLM; name='facebook/nllb-200-distilled-600M'; AutoTokenizer.from_pretrained(name); AutoModelForSeq2SeqLM.from_pretrained(name); print('LOCAL NLLB MODEL READY')"

Write-Host ""
Write-Host "==============================================="
Write-Host " FREE LOCAL TRANSLATION SETUP COMPLETE"
Write-Host "==============================================="
Write-Host ""
Write-Host "Next: run fix_translation_backend_local_nllb.py"
Write-Host ""
