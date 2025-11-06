# ClickUp Lead Optimizer

This repository contains the `clickupLeadOptimizer`, a tool for processing and qualifying ClickUp leads for the Compass and Upcurve sales teams. The primary functions are to determine a lead's non-profit status and their Organization Type.

## Business Rules

### Profit/Non-profit Status Determination

The system determines a lead's 'Profit/Non-profit' status through the following steps:

1.  **ProPublica API Check:** The system first queries the ProPublica Non-Profit Explorer API using the organization's name. If a match is found, the organization is marked as a non-profit, and its details (EIN, name, location, etc.) are recorded.
2.  **IRS EIN Check:** If the lead has an EIN (Employer Identification Number), the system validates its format. *Note: The current implementation only checks the format of the EIN and does not perform a full lookup against the IRS database.*
3.  **Website Scraping:** The system scrapes the organization's website (if available) for keywords and phrases that indicate non-profit status. These include terms like "501(c)(3)", "non-profit", "charity", "donation", etc. The presence of these indicators is used as a strong signal of non-profit status, especially when an API lookup fails.

### Sales Team Assignment: Compass vs. Upcurve

Leads are assigned to either the 'Compass' or 'Upcurve' sales teams based on a scoring system. A lead is evaluated for each product, and the product with the higher score is considered the 'best fit'.

#### Compass Scoring

The 'Compass' product is targeted at residential program management. The scoring logic for Compass is as follows:

*   **Keywords:** The system scans the organization's website and other text data for keywords related to residential programs, such as 'halfway house', 'recovery', 'sober living', 'residential', etc.
*   **Organization Type:** A higher score is awarded if the organization's type is identified as 'halfway\_house', 'recovery\_center', 'sober\_living', or 'group\_home'.
*   **Non-profit Status:** The score is boosted if the organization is a non-profit.
*   **Residential Component:** The score is increased if the website content mentions residential components like 'resident', 'housing', 'beds', or 'capacity'.
*   **Multiple Locations:** A small bonus is added if there is evidence of multiple locations.

#### Upcurve Scoring

The 'Upcurve' product is a fundraising platform for non-profits. The scoring logic for Upcurve is as follows:

*   **Non-profit Requirement:** A lead **must** be identified as a non-profit to be considered for Upcurve.
*   **Keywords:** The system scans for keywords related to fundraising and non-profit activities, such as 'nonprofit', '501c3', 'charity', 'foundation', 'fundraising', etc.
*   **Donation Page:** A significant score boost is given if the organization's website has a donation page.
*   **Organization Size:** An additional boost is given to smaller organizations (under $5M in revenue) as they are considered to be in greater need of fundraising tools.
*   **Newer Non-profits:** A small bonus is added for non-profits established in recent years (after 2018).
