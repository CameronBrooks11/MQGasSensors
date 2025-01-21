import cv2
import numpy as np
import matplotlib.pyplot as plt
import os
from scipy.stats import linregress

# Prompt for run name
run_name = input("Enter a name for this run: ").strip()
if not run_name:
    run_name = "default"

# Prepare the log file path (ensure it's in the same directory as the script)
script_dir = os.path.dirname(os.path.abspath(__file__))
log_filename = "results_regressAB.txt"
log_path = os.path.join(script_dir, log_filename)

# Variables for controlling the script
image_filename = "mq_137_sensitivity_curve.png"  # Change this to your image filename
lo_diff = 20
up_diff = 20
bin_width = 5  # Adjust as needed

# Load the image
image_path = os.path.join(script_dir, image_filename)
image_color = cv2.imread(image_path)

if image_color is None:
    raise FileNotFoundError(f"Image not found at path: {image_path}")

# Display the image to help the user determine the axes ranges
plt.figure(figsize=(10, 6))
plt.imshow(cv2.cvtColor(image_color, cv2.COLOR_BGR2RGB))
plt.title("Loaded Image for Reference")
plt.axis("off")
plt.show()

# Prompt the user for x and y ranges
print("Please enter the axes ranges of the chart in the image.")
print(
    "For logarithmic scales, enter the minimum and maximum values displayed on the axes."
)

# X-axis ranges (e.g., Gas Concentration in PPM)
ppm_min = float(input("Enter x-axis minimum value (ppm_min): "))
ppm_max = float(input("Enter x-axis maximum value (ppm_max): "))

# Y-axis ranges (e.g., Rs/R0)
rsr0_min = float(input("Enter y-axis minimum value (rsr0_min): "))
rsr0_max = float(input("Enter y-axis maximum value (rsr0_max): "))

# Variables to hold the seed point and flood fill difference
seed_point = None

# Create a copy of the image for display
image_display = image_color.copy()


# Mouse callback function to get the seed point
def mouse_callback(event, x, y, flags, param):
    global seed_point, image_display
    if event == cv2.EVENT_LBUTTONDOWN:
        seed_point = (x, y)
        # Refresh the display image
        image_display = image_color.copy()
        # Draw a circle at the seed point
        cv2.circle(image_display, seed_point, 3, (0, 0, 255), -1)
        # Update the flood fill visualization
        update_flood_fill()


# Function to update the flood fill visualization
def update_flood_fill(*args):
    global image_display, seed_point, lo_diff, up_diff
    if seed_point is None:
        return
    # Read the values from the trackbars
    lo_diff = cv2.getTrackbarPos("lo_diff", "Flood Fill")
    up_diff = cv2.getTrackbarPos("up_diff", "Flood Fill")
    # Create a mask
    h, w = image_color.shape[:2]
    mask = np.zeros((h + 2, w + 2), np.uint8)
    # Copy the image for flood fill
    flooded_image = image_color.copy()
    # Perform flood fill
    flags = cv2.FLOODFILL_FIXED_RANGE
    cv2.floodFill(
        flooded_image,
        mask,
        seed_point,
        (255, 255, 255),
        (lo_diff, lo_diff, lo_diff),
        (up_diff, up_diff, up_diff),
        flags,
    )
    # Extract the mask (remove the extra border)
    floodfill_mask = mask[1:-1, 1:-1]
    # Create an image showing the flood filled area
    floodfill_vis = cv2.bitwise_and(image_color, image_color, mask=floodfill_mask)
    # Overlay the seed point
    cv2.circle(floodfill_vis, seed_point, 3, (0, 0, 255), -1)
    # Show the flood filled image
    cv2.imshow("Flood Fill", floodfill_vis)


# Create a window and set mouse callback
cv2.namedWindow("Flood Fill")
cv2.setMouseCallback("Flood Fill", mouse_callback)
# Create trackbars for lo_diff and up_diff
cv2.createTrackbar("lo_diff", "Flood Fill", lo_diff, 100, update_flood_fill)
cv2.createTrackbar("up_diff", "Flood Fill", up_diff, 100, update_flood_fill)

# Display instructions
print("\nClick on a point on the target curve to set the seed point.")
print("Use the trackbars to adjust 'lo_diff' and 'up_diff'.")
print("Press 's' to proceed when satisfied, or 'q' to quit.")

while True:
    if seed_point is None:
        # Show the image without flood fill
        cv2.imshow("Flood Fill", image_display)
    key = cv2.waitKey(1) & 0xFF
    if key == ord("s"):
        # Proceed to next step
        break
    elif key == ord("q") or key == 27:
        # Quit
        cv2.destroyAllWindows()
        exit()

cv2.destroyAllWindows()

# Use the last floodfill_mask generated
h, w = image_color.shape[:2]
mask = np.zeros((h + 2, w + 2), np.uint8)
flags = cv2.FLOODFILL_FIXED_RANGE
cv2.floodFill(
    image_color.copy(),
    mask,
    seed_point,
    (255, 255, 255),
    (lo_diff, lo_diff, lo_diff),
    (up_diff, up_diff, up_diff),
    flags,
)
floodfill_mask = mask[1:-1, 1:-1]

# Get the indices of the non-zero pixels in the mask
y_indices, x_indices = np.nonzero(floodfill_mask)

# Remove duplicates (if any)
points = np.column_stack((x_indices, y_indices))
points = np.unique(points, axis=0)

# Visualization: Show the detected curve on the original image
plt.figure(figsize=(10, 6))
plt.imshow(cv2.cvtColor(image_color, cv2.COLOR_BGR2RGB))
plt.scatter(points[:, 0], points[:, 1], c="red", s=1)
plt.title("Detected Curve Points")
plt.xlabel("Pixel X")
plt.ylabel("Pixel Y")
plt.gca().invert_yaxis()  # Invert y-axis to match image coordinate system
plt.show()

# Bin the x-values
x_min_pixel = points[:, 0].min()
x_max_pixel = points[:, 0].max()
bins = np.arange(x_min_pixel, x_max_pixel + bin_width, bin_width)

# Digitize the x-values
indices = np.digitize(points[:, 0], bins)

# Calculate the average y-value for each bin
x_bin_centers = []
y_bin_averages = []

for i in range(1, len(bins)):
    bin_points = points[indices == i]
    if len(bin_points) > 0:
        x_center = bins[i - 1] + bin_width / 2
        y_average = bin_points[:, 1].mean()
        x_bin_centers.append(x_center)
        y_bin_averages.append(y_average)

x_bin_centers = np.array(x_bin_centers)
y_bin_averages = np.array(y_bin_averages)

# Visualization: Plot the averaged points
plt.figure(figsize=(10, 6))
plt.imshow(cv2.cvtColor(image_color, cv2.COLOR_BGR2RGB))
plt.scatter(x_bin_centers, y_bin_averages, c="yellow", s=5, label="Averaged Points")
plt.title("Averaged Curve Points")
plt.xlabel("Pixel X")
plt.ylabel("Pixel Y")
plt.gca().invert_yaxis()
plt.legend()
plt.show()

# Convert pixel coordinates to data coordinates with logarithmic scales

# Pixel ranges corresponding to the graph axes
x_pixel_min, x_pixel_max = x_bin_centers.min(), x_bin_centers.max()
y_pixel_min, y_pixel_max = y_bin_averages.max(), y_bin_averages.min()  # Inverted y-axis

# Map pixel coordinates to logarithmic data coordinates
ppm_log = np.log10(ppm_min) + (x_bin_centers - x_pixel_min) * (
    np.log10(ppm_max) - np.log10(ppm_min)
) / (x_pixel_max - x_pixel_min)
rsr0_log = np.log10(rsr0_min) + (y_bin_averages - y_pixel_min) * (
    np.log10(rsr0_max) - np.log10(rsr0_min)
) / (y_pixel_max - y_pixel_min)

# Convert log data back to actual values
ppm_data = 10**ppm_log
rsr0_data = 10**rsr0_log

# Remove any NaN or infinite values
valid_indices = np.isfinite(ppm_data) & np.isfinite(rsr0_data)
ppm_data = ppm_data[valid_indices]
rsr0_data = rsr0_data[valid_indices]
x_bin_centers = x_bin_centers[valid_indices]
y_bin_averages = y_bin_averages[valid_indices]

# Take logarithm for linear regression
x = np.log10(ppm_data)
y = np.log10(rsr0_data)

# Perform linear regression
slope, intercept, r_value, p_value, std_err = linregress(x, y)

# Extract A and B
B = slope
logA = intercept
A = 10**logA

print(f"\nExtracted parameters:")
print(f"A = {A:.4f}")
print(f"B = {B:.4f}")

# Save results to log file
with open(log_path, "a") as f:
    f.write(f"=== Run name: {run_name} ===\n")
    f.write(f"Image filename: {image_filename}\n")
    f.write(f"A = {A:.4f}\n")
    f.write(f"B = {B:.4f}\n")
    f.write(f"lo_diff = {lo_diff}\n")
    f.write(f"up_diff = {up_diff}\n")
    f.write(f"bin_width = {bin_width}\n")
    f.write(f"ppm_min = {ppm_min}, ppm_max = {ppm_max}\n")
    f.write(f"rsr0_min = {rsr0_min}, rsr0_max = {rsr0_max}\n")
    f.write(f"slope = {slope}\n")
    f.write(f"intercept = {intercept}\n")
    f.write(f"r_value = {r_value}\n")
    f.write(f"p_value = {p_value}\n")
    f.write(f"std_err = {std_err}\n")
    f.write("\n")  # Add a blank line between entries

print(f"\nResults appended to {log_filename}")

# Plotting the data and the fitted line
plt.figure(figsize=(10, 6))
plt.scatter(x, y, label="Data Points")
plt.plot(x, intercept + slope * x, "r", label="Fitted Line")
plt.xlabel("log10(PPM)")
plt.ylabel("log10(Rs/R0)")
plt.title("Linear Regression on Log-Transformed Data")
plt.legend()
plt.grid(True)
plt.show()

# Plot the fitted curve on the original scale
plt.figure(figsize=(10, 6))
plt.loglog(ppm_data, rsr0_data, "bo", markersize=5, label="Extracted Data Points")
ppm_fit = np.logspace(np.log10(ppm_data.min()), np.log10(ppm_data.max()), 500)
rsr0_fit = A * ppm_fit**B
plt.loglog(
    ppm_fit,
    rsr0_fit,
    "r-",
    linewidth=2,
    label=f"Fitted Curve: Rs/R0 = {A:.2f} * PPM^{B:.2f}",
)
plt.title("Fitted Curve on Log-Log Scale")
plt.xlabel("Gas Concentration (PPM)")
plt.ylabel("Rs/R0")
plt.legend()
plt.grid(True, which="both", ls="--")
plt.show()

# Map the fitted curve back to pixel coordinates
ppm_fit_log = np.log10(ppm_fit)
rsr0_fit_log = np.log10(rsr0_fit)

# Map data coordinates back to pixel coordinates
x_pixel_fit = x_pixel_min + (ppm_fit_log - np.log10(ppm_min)) * (
    x_pixel_max - x_pixel_min
) / (np.log10(ppm_max) - np.log10(ppm_min))
y_pixel_fit = y_pixel_min + (rsr0_fit_log - np.log10(rsr0_min)) * (
    y_pixel_max - y_pixel_min
) / (np.log10(rsr0_max) - np.log10(rsr0_min))

# Prepare to overlay the curve on the original image
image_with_curve = cv2.cvtColor(image_color.copy(), cv2.COLOR_BGR2RGB)

# Ensure that pixel values are within image bounds
x_pixel_fit = np.clip(x_pixel_fit, 0, image_with_curve.shape[1] - 1)
y_pixel_fit = np.clip(y_pixel_fit, 0, image_with_curve.shape[0] - 1)

# Convert coordinates to integer pixels
x_pixel_fit = x_pixel_fit.astype(np.int32)
y_pixel_fit = y_pixel_fit.astype(np.int32)

# Draw the fitted curve on the image
for i in range(len(x_pixel_fit) - 1):
    cv2.line(
        image_with_curve,
        (x_pixel_fit[i], y_pixel_fit[i]),
        (x_pixel_fit[i + 1], y_pixel_fit[i + 1]),
        color=(0, 255, 0),
        thickness=2,
    )

# Plot the image with the superimposed fitted curve
plt.figure(figsize=(10, 6))
plt.imshow(image_with_curve)
plt.scatter(x_bin_centers, y_bin_averages, c="yellow", s=5, label="Averaged Points")
plt.title("Fitted Curve Superimposed on Original Image")
plt.xlabel("Pixel X")
plt.ylabel("Pixel Y")
plt.gca().invert_yaxis()
plt.legend()
plt.show()
