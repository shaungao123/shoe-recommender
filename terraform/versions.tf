terraform {
  required_version = ">= 1.9"

  # Remote state in HCP Terraform (free tier). State is shared and locked, so a
  # second `apply` can't race the first. Set this workspace's Execution Mode to
  # "Local" in the HCP UI so plan/apply run here and pick up TF_VAR_do_token.
  cloud {
    organization = "ShoeApp"

    workspaces {
      name = "shoe-recommender"
    }
  }

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.43"
    }
  }
}

provider "digitalocean" {
  token = var.do_token
}
