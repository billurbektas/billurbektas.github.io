# Install and load required packages
if (!require("visNetwork")) install.packages("visNetwork")
if (!require("htmlwidgets")) install.packages("htmlwidgets")

library(visNetwork)
library(htmlwidgets)

# Create sample data - ensuring all fields are properly formatted as arrays
nodes <- data.frame(
  id = 1:5,  # Simplified dataset for testing
  label = c("Billur Bektas", 
            "John Smith", 
            "Maria Garcia",
            "David Chen",
            "Sarah Williams"),
  group = c("PI", 
            "Collaborator",
            "Collaborator",
            "Collaborator",
            "Collaborator"),
  institution = c("MIT",
                  "Harvard",
                  "Stanford",
                  "MIT",
                  "Berkeley"),
  type = c("PI",
           "Co-author",
           "Student",
           "Co-author",
           "Supervision"),
  stringsAsFactors = FALSE  # Important: prevent automatic factor conversion
)

edges <- data.frame(
  from = c(1,1,1,2,3),
  to = c(2,3,4,3,4),
  type = c("Co-author",
           "Supervision",
           "Co-author",
           "Project",
           "Collaboration"),
  width = c(3,2,3,1,2),
  stringsAsFactors = FALSE  # Important: prevent automatic factor conversion
)

# Create a simple network first to test
network <- visNetwork(nodes, edges) %>%
  visOptions(
    highlightNearest = TRUE,
    selectedBy = "institution"  # Simplified selection option
  ) %>%
  visLayout(randomSeed = 123)

# Save the network
saveWidget(network, "collaboration_network.html", selfcontained = TRUE)