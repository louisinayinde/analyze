terraform {
  backend "gcs" {
    bucket = "analyze-app-prod-tfstate"
    prefix = "secrets"
  }
}
