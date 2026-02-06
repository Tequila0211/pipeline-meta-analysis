# 09_meta.R - Meta-Analysis Script

# Check if metafor is installed
if (!require("metafor")) install.packages("metafor")
library(metafor)

# Load data
data <- read.csv("exports/unified_outcomes.csv")

# Filter for primary eligible outcomes (example filter)
# In real scenario, would filter by eligible_primary and is_primary
# For MVP, we take all

if (nrow(data) > 0) {
  # Calculate Effect Sizes (here assuming raw Mean Difference as we have diffs)
  # For proper SMD we need SD/N, but for MVP we demonstrate syntax
  
  # Example: Random Effects Model on raw_diff
  # yi = raw_diff
  # vi = variance (needs to be calculated or imputed since we mostly have means)
  # For demo purposes, we will impute small variance if missing
  
  data$yi <- data$raw_diff
  data$vi <- ifelse(is.na(data$variance_value), 0.1, data$variance_value) # DUMMY VARIANCE
  
  res <- rma(yi, vi, data=data, method="REML")
  
  print(summary(res))
  
  # Forest Plot
  png("exports/forest_plot.png")
  forest(res)
  dev.off()
  
  # Funnel Plot
  png("exports/funnel_plot.png")
  funnel(res)
  dev.off()
  
  print("Meta-analysis completed. Plots saved in exports/")
} else {
  print("No data available for meta-analysis.")
}
