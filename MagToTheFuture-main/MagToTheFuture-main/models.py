import torch.nn as nn

class MLP(nn.Module):
    def __init__(self, input_size=72, output_size=3, hidden_size=256, dropout_rate=0.2):
        super(MLP, self).__init__()
        
        self.layers = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            
            nn.Linear(hidden_size, 128),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            
            nn.Linear(128, 64),
            nn.ReLU(),
            
            nn.Linear(64, output_size)
        )

    def forward(self, x):
        return self.layers(x)

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