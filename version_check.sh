echo "========== Jetson Version Info =========="
echo "[Python]"
python3 --version

echo
echo "[JetPack]"
dpkg-query --show nvidia-l4t-core | awk '{print $2}' | sed 's/^/JetPack version inferred from L4T version: /'

echo
echo "[CUDA]"
nvcc --version | grep release || cat /usr/local/cuda/version.txt

echo
echo "[cuDNN]"
cat /usr/include/cudnn_version.h | grep CUDNN_MAJOR -A 2

echo
echo "[PyTorch]"
python3 -c "import torch; print('PyTorch:', torch.__version__); print('CUDA:', torch.version.cuda); print('cuDNN:', torch.backends.cudnn.version())"
