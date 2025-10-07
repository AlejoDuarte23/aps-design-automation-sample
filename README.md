# APS Design Automation Workflows in python

Complete workflow implementation for Autodesk Platform Services (APS) Design Automation API. This is a Python implementation of the official tutorial: https://aps.autodesk.com/en/docs/design-automation/v3/tutorials/revit/about_this_tutorial

## Prerequisites

1. APS Application credentials (Client ID & Secret)
2. Python 3.8+
3. Required packages: `pip install requests python-dotenv`

## Environment Setup

Create a `.env` file in the project root:

```env
CLIENT_ID=your_client_id_here
CLIENT_SECRET=your_client_secret_here
```
## Download Files

The following files need to be downloaded to run the example. Create a folder named `files` in the root of the repo:

- [Delete all wall bundle](https://github.com/autodesk-platform-services/aps-tutorial-postman/blob/f8469f1bf0a5dd53e8e7193c0e5a1f1e0604c3d6/DA4Revit/walkthrough_data/DeleteWallsApp.zip)
- [Revit file](https://github.com/autodesk-platform-services/aps-tutorial-postman/blob/f8469f1bf0a5dd53e8e7193c0e5a1f1e0604c3d6/DA4Revit/walkthrough_data/DeleteWalls.rvt)