terraform {
  required_providers {
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 1.15"
    }
  }
}

variable "atlas_public_key"  { type = string }
variable "atlas_private_key" { type = string }
variable "atlas_org_id"      { type = string }

provider "mongodbatlas" {
  public_key  = var.atlas_public_key
  private_key = var.atlas_private_key
}

resource "mongodbatlas_project" "nosql_lab13" {
  name   = "NoSQL-Lab13-Production"
  org_id = var.atlas_org_id
}

resource "mongodbatlas_cluster" "free_tier" {
  project_id                  = mongodbatlas_project.nosql_lab13.id
  name                        = "Cluster0-FreeTier"
  provider_name               = "TENANT"
  backing_provider_name       = "AWS"
  provider_region_name        = "AP_SOUTH_1"
  provider_instance_size_name = "M0"
}