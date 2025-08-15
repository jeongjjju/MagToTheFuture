import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset, random_split
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
import joblib
import os

df = pd.read_csv('./data/processed_training_data_all.csv')

X = df.drop(columns=['is_tracker', 'timestamp', 'tracker_rot_roll', 'tracker_rot_pitch', 'tracker_rot_yaw', 'tracker_pos_x', 'tracker_pos_y', 'tracker_pos_z'], errors='ignore')
y = df['is_tracker']

X_tensor = torch.tensor(X.values, dtype=torch.float32)
y_tensor = torch.tensor(y.values, dtype=torch.float32).view(-1, 1)

dataset = TensorDataset(X_tensor, y_tensor)
train_size = int(0.8 * len(dataset))
val_size = len(dataset) - train_size
train_ds, val_ds = random_split(dataset, [train_size, val_size])

train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)
val_loader = DataLoader(val_ds, batch_size=64)

class PresenceDetector(nn.Module):
    def __init__(self, input_size):
        super(PresenceDetector, self).__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_size, 64), nn.ReLU(),
            nn.Linear(64, 32), nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )
    def forward(self, x):
        return self.layers(x)

model = PresenceDetector(input_size=X_tensor.shape[1])

criterion = nn.BCELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
epochs = 20

for epoch in range(epochs):
    model.train()
    train_loss = 0
    for xb, yb in train_loader:
        optimizer.zero_grad()
        preds = model(xb)
        loss = criterion(preds, yb)
        loss.backward()
        optimizer.step()
        train_loss += loss.item() * xb.size(0)
    
    train_loss /= len(train_loader.dataset)

    model.eval()
    val_preds = []
    val_targets = []
    with torch.no_grad():
        for xb, yb in val_loader:
            preds = model(xb)
            val_preds.extend(preds.cpu().numpy())
            val_targets.extend(yb.cpu().numpy())
    
    val_preds_binary = [1 if p > 0.5 else 0 for p in val_preds]
    val_acc = accuracy_score(val_targets, val_preds_binary)

    print(f"Epoch {epoch+1:02d} | Train Loss: {train_loss:.4f} | Val Acc: {val_acc:.4f}")


save_dir = './models'
os.makedirs(save_dir, exist_ok=True)
model_save_path = os.path.join(save_dir, 'presence_detector_20250727_224824.pth')

torch.save(model.state_dict(), model_save_path)
print(f"Classifier model saved to: {model_save_path}")
