import pandas as pd
import matplotlib.pyplot as plt

# Load loss history
df = pd.read_csv('/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/loss_curve.csv')

# Plot
# Load test loss
with open('/GridCalEngine/Simulations/SCOPF_GNN/ModelTraining/test_loss.txt', 'r') as f:
    test_loss = float(f.read())

# Plot
plt.figure(figsize=(10, 6))
plt.plot(df['train_loss'], label='Train Loss')
plt.plot(df['val_loss'], label='Validation Loss')
plt.axhline(test_loss, color='red', linestyle='--', label=f'Test Loss ({test_loss:.4f})')

plt.xlabel("Epoch")
plt.ylabel("Loss")
plt.title("Training vs Validation vs Test Loss")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig("loss_curve_with_test.png")
plt.show()







