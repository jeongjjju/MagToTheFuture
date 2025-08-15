import pandas as pd
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import matplotlib.pyplot as plt

from models import MLP

data_dir = './data'
model_dir = './models'
time_stamp = '20250727_224824'
INPUT_CSV_PATH = f'{data_dir}/processed_training_data_all.csv'
MODEL_SAVE_PATH = f'{model_dir}/hall_sensor_model_{time_stamp}.pth'
INPUT_SIZE = 72
OUTPUT_SIZE = 3
LEARNING_RATE = 0.001
BATCH_SIZE = 64
EPOCHS = 100
TEST_SPLIT_RATIO = 0.2

PATIENCE = 10
early_stopping_counter = 0
best_val_loss = np.inf

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")


print("Loading and preprocessing data...")
try:
    data = pd.read_csv(INPUT_CSV_PATH)
    data = data[data['is_tracker'] == 1]
except FileNotFoundError:
    print(f"Error: '{INPUT_CSV_PATH}' not found. Please run the preprocessing script first.")
    exit()

exclude_cols = [col for col in data.columns if col.startswith(('tracker_pos', 'timestamp', 'tracker_rot_', 'is_tracker'))]
X = data.drop(columns=exclude_cols)
y = data[['tracker_pos_x', 'tracker_pos_y', 'tracker_pos_z']]

X_tensor = torch.tensor(X.values, dtype=torch.float32)
y_tensor = torch.tensor(y.values, dtype=torch.float32)

X_train, X_val, y_train, y_val = train_test_split(
    X_tensor, y_tensor, test_size=TEST_SPLIT_RATIO, random_state=42
)

train_dataset = TensorDataset(X_train, y_train)
train_loader = DataLoader(dataset=train_dataset, batch_size=BATCH_SIZE, shuffle=True)

val_dataset = TensorDataset(X_val, y_val)
val_loader = DataLoader(dataset=val_dataset, batch_size=BATCH_SIZE, shuffle=False)

print(f"Data loaded. Training samples: {len(X_train)}, Validation samples: {len(X_val)}")


model = MLP(input_size=INPUT_SIZE, output_size=OUTPUT_SIZE).to(device)
criterion = nn.MSELoss()
optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)


print("\nStarting training...")
train_loss_history = []
val_loss_history = []

for epoch in range(EPOCHS):
    model.train()
    train_loss = 0.0
    for inputs, labels in train_loader:
        inputs, labels = inputs.to(device), labels.to(device)
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        train_loss += loss.item()

    model.eval()
    val_loss = 0.0
    all_preds = []
    all_labels = []
    with torch.no_grad():
        for inputs, labels in val_loader:
            inputs, labels = inputs.to(device), labels.to(device)
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            val_loss += loss.item()
            all_preds.append(outputs.cpu())
            all_labels.append(labels.cpu())

    avg_train_loss = train_loss / len(train_loader)
    avg_val_loss = val_loss / len(val_loader)
    
    train_loss_history.append(avg_train_loss)
    val_loss_history.append(avg_val_loss)

    val_mae = mean_absolute_error(torch.cat(all_labels), torch.cat(all_preds))

    print(f"Epoch [{epoch+1}/{EPOCHS}], Train Loss: {avg_train_loss:.6f}, Val Loss: {avg_val_loss:.6f}, Val MAE: {val_mae:.6f}")
    if avg_val_loss < best_val_loss:
        best_val_loss = avg_val_loss
        torch.save(model.state_dict(), MODEL_SAVE_PATH)
        early_stopping_counter = 0
        print(f"Validation loss improved. Model saved to '{MODEL_SAVE_PATH}'")
    else:
        early_stopping_counter += 1

    if early_stopping_counter >= PATIENCE:
        print(f"\nEarly stopping triggered after {epoch + 1} epochs.")
        break

plt.figure(figsize=(10, 5))
plt.plot(train_loss_history, label='Train Loss')
plt.plot(val_loss_history, label='Validation Loss')
plt.title('Model Loss During Training')
plt.xlabel('Epoch')
plt.ylabel('Loss')
plt.legend()
plt.grid(True)
plt.savefig(f'{model_dir}/loss_graph_{time_stamp}.png')
print(f"Loss graph saved to '{model_dir}/loss_graph_{time_stamp}.png'")

print(f"\nTraining finished. Model saved to '{MODEL_SAVE_PATH}'")

print("\nVisualizing validation results...")

best_model = MLP(input_size=INPUT_SIZE, output_size=OUTPUT_SIZE).to(device)
best_model.load_state_dict(torch.load(MODEL_SAVE_PATH))
best_model.eval()

with torch.no_grad():
    val_predictions = best_model(X_val.to(device)).cpu()

num_samples = len(y_val)
num_to_plot = min(5, num_samples)
random_indices = np.random.choice(num_samples, size=num_to_plot, replace=False)

actual_samples = y_val[random_indices]
predicted_samples = val_predictions[random_indices]

plt.figure(figsize=(8, 8))
plt.scatter(actual_samples[:, 0], actual_samples[:, 2], c='blue', marker='o', label='Actual Position', s=100, zorder=5)
plt.scatter(predicted_samples[:, 0], predicted_samples[:, 2], c='red', marker='x', label='Predicted Position', s=100, zorder=5)

for i in range(num_to_plot):
    plt.plot([actual_samples[i, 0], predicted_samples[i, 0]],
             [actual_samples[i, 2], predicted_samples[i, 2]],
             'k--', alpha=0.5)

plt.title('Actual vs. Predicted Positions (Top-Down View)')
plt.xlabel('X coordinate')
plt.ylabel('Z coordinate')
plt.legend()
plt.grid(True)
plt.gca().set_aspect('equal', adjustable='box')

viz_save_path = f'{model_dir}/validation_visualization_{time_stamp}.png'
plt.savefig(viz_save_path)
print(f"Validation visualization saved to '{viz_save_path}'")