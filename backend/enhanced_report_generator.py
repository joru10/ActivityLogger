"""
Enhanced report generator that creates rich HTML reports with multiple visualizations.
This module provides functions to generate comprehensive weekly reports with all required visualizations.
"""

import json
import logging
from datetime import datetime, date
from pathlib import Path
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the reports directory
REPORTS_DIR = Path(__file__).parent.parent / "reports"
WEEKLY_REPORTS_DIR = REPORTS_DIR / "weekly"

def generate_enhanced_html_report(report_data):
    """
    Generate an enhanced HTML report with multiple visualizations.

    Args:
        report_data: The report data dictionary

    Returns:
        HTML string containing the report with all visualizations
    """
    # Extract data from the report
    executive_summary = report_data.get("executive_summary", {})
    total_time = executive_summary.get("total_time", 0)
    time_by_group = executive_summary.get("time_by_group", {})
    time_by_category = executive_summary.get("time_by_category", {})
    daily_breakdown = executive_summary.get("daily_breakdown", {})
    details = report_data.get("details", [])

    # Format time as hours and minutes
    hours = total_time // 60
    minutes = total_time % 60
    time_display = f"{hours} hours {minutes} minutes"

    # Prepare data for daily activity distribution chart
    days = sorted(daily_breakdown.keys())
    daily_times = [daily_breakdown[day].get("total_time", 0) for day in days]
    formatted_days = [datetime.strptime(day, "%Y-%m-%d").strftime("%a %m-%d") for day in days]

    # Prepare data for time by group table
    time_by_group_html = ""
    for group, minutes in time_by_group.items():
        group_hours = minutes // 60
        group_minutes = minutes % 60
        time_by_group_html += f"<tr><td>{group}</td><td>{group_hours} hours {group_minutes} minutes</td></tr>"

    # Prepare data for time by category table
    time_by_category_html = ""
    for category, minutes in time_by_category.items():
        category_hours = minutes // 60
        category_minutes = minutes % 60
        time_by_category_html += f"<tr><td>{category}</td><td>{category_hours} hours {category_minutes} minutes</td></tr>"

    # Create HTML for daily breakdown
    daily_breakdown_html = ""
    for day, data in sorted(daily_breakdown.items()):
        day_date = datetime.strptime(day, "%Y-%m-%d").strftime("%A, %B %d, %Y")
        day_total = data.get("total_time", 0)
        day_hours = day_total // 60
        day_minutes = day_total % 60

        # Create HTML for groups in this day
        day_groups_html = ""
        for group, minutes in data.get("time_by_group", {}).items():
            group_hours = minutes // 60
            group_minutes = minutes % 60
            day_groups_html += f"<tr><td>{group}</td><td>{group_hours} hours {group_minutes} minutes</td></tr>"

        # Create HTML for categories in this day
        day_categories_html = ""
        for category, minutes in data.get("time_by_category", {}).items():
            category_hours = minutes // 60
            category_minutes = minutes % 60
            day_categories_html += f"<tr><td>{category}</td><td>{category_hours} hours {category_minutes} minutes</td></tr>"

        daily_breakdown_html += f"""
        <div class="day-section">
            <h3>{day_date}</h3>
            <p>Total time: {day_hours} hours {day_minutes} minutes</p>
            <div class="day-tables">
                <div class="day-table">
                    <h4>Time by Group</h4>
                    <table class="group-table">
                        <thead>
                            <tr>
                                <th>Group</th>
                                <th>Time</th>
                            </tr>
                        </thead>
                        <tbody>
                            {day_groups_html}
                        </tbody>
                    </table>
                </div>
                <div class="day-table">
                    <h4>Time by Category</h4>
                    <table class="category-table">
                        <thead>
                            <tr>
                                <th>Category</th>
                                <th>Time</th>
                            </tr>
                        </thead>
                        <tbody>
                            {day_categories_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        """

    # Create HTML for activity log
    activity_log_html = ""
    for activity in details:
        timestamp = activity.get("timestamp", "")
        if timestamp:
            try:
                formatted_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d %H:%M")
            except ValueError:
                formatted_time = timestamp
        else:
            formatted_time = ""

        group = activity.get("group", "")
        category = activity.get("category", "")
        duration = activity.get("duration_minutes", 0)
        description = activity.get("description", "")

        activity_log_html += f"""
        <tr>
            <td>{formatted_time}</td>
            <td>{group}</td>
            <td>{category}</td>
            <td>{duration} minutes</td>
            <td>{description}</td>
        </tr>
        """

    # Generate the full HTML report
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Weekly Activity Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1, h2, h3, h4 {{
                color: #2c3e50;
            }}
            .section {{
                margin-bottom: 30px;
                border: 1px solid #eee;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .day-section {{
                margin-bottom: 20px;
                padding: 15px;
                background-color: #f9f9f9;
                border-radius: 5px;
            }}
            .day-tables {{
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
            }}
            .day-table {{
                flex: 1;
                min-width: 300px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 20px;
            }}
            th, td {{
                padding: 12px 15px;
                border-bottom: 1px solid #ddd;
                text-align: left;
            }}
            th {{
                background-color: #f8f9fa;
                font-weight: bold;
            }}
            tr:hover {{
                background-color: #f5f5f5;
            }}
            .chart-container {{
                height: 400px;
                margin-bottom: 30px;
            }}
            .charts-row {{
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
                margin-bottom: 30px;
            }}
            .chart-box {{
                flex: 1;
                min-width: 45%;
                height: 400px;
                padding: 15px;
                background-color: #f9f9f9;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .summary-stats {{
                display: flex;
                justify-content: space-between;
                flex-wrap: wrap;
                margin-bottom: 20px;
            }}
            .stat-card {{
                flex: 1;
                min-width: 200px;
                margin: 10px;
                padding: 15px;
                background-color: #f8f9fa;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                text-align: center;
            }}
            .stat-card h3 {{
                margin-top: 0;
                color: #3498db;
            }}
            .stat-card p {{
                font-size: 1.5em;
                font-weight: bold;
                margin: 10px 0;
            }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>
    <body>
        <h1>Weekly Activity Report</h1>

        <div class="section">
            <h2>Executive Summary</h2>

            <div class="summary-stats">
                <div class="stat-card">
                    <h3>Total Time</h3>
                    <p>{time_display}</p>
                </div>
                <div class="stat-card">
                    <h3>Activities</h3>
                    <p>{len(details)}</p>
                </div>
                <div class="stat-card">
                    <h3>Groups</h3>
                    <p>{len(time_by_group)}</p>
                </div>
            </div>

            <h3>Visualizations</h3>

            <div class="chart-container">
                <canvas id="dailyActivityChart"></canvas>
            </div>

            <div class="charts-row">
                <div class="chart-box">
                    <canvas id="categoryGroupChart"></canvas>
                </div>
                <div class="chart-box">
                    <canvas id="categoryGroupDoughnut"></canvas>
                </div>
            </div>

            <h3>Time by Group</h3>
            <table>
                <thead>
                    <tr>
                        <th>Group</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody>
                    {time_by_group_html}
                </tbody>
            </table>

            <h3>Time by Category</h3>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody>
                    {time_by_category_html}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Daily Breakdown</h2>
            {daily_breakdown_html}
        </div>

        <div class="section">
            <h2>Activity Log</h2>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Group</th>
                        <th>Category</th>
                        <th>Duration</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
                    {activity_log_html}
                </tbody>
            </table>
        </div>

        <script>
            // Create chart for daily activity
            const dailyCtx = document.getElementById('dailyActivityChart').getContext('2d');
            const dailyActivityChart = new Chart(dailyCtx, {{
                type: 'bar',
                data: {{
                    labels: {json.dumps(formatted_days)},
                    datasets: [{{
                        label: 'Minutes',
                        data: {json.dumps(daily_times)},
                        backgroundColor: 'rgba(54, 162, 235, 0.7)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            title: {{
                               display: true,
                                text: 'Minutes'
                            }}
                        }}
                    }},
                    plugins: {{
                        title: {{
                            display: true,
                            text: 'Daily Activity Distribution',
                            font: {{
                                size: 16
                            }}
                        }},
                        legend: {{
                            display: true
                        }}
                    }}
                }}
            }});

            // Function to generate distinct colors
            function getDistinctColors(count) {{
                const colors = [];
                for (let i = 0; i < count; i++) {{
                    const hue = i / count;
                    const r = Math.floor(((Math.sin(hue * 6.28) * 0.5) + 0.5) * 200) + 55;
                    const g = Math.floor(((Math.sin((hue * 6.28) + 2.09) * 0.5) + 0.5) * 200) + 55;
                    const b = Math.floor(((Math.sin((hue * 6.28) + 4.19) * 0.5) + 0.5) * 200) + 55;
                    colors.push(`rgba(${{r}}, ${{g}}, ${{b}}, 0.7)`);
                }}
                return colors;
            }}

            // Create chart for category-group distribution (stacked bar chart)
            // This will be populated from the visualization data if available
            console.log('EXTREMELY OBVIOUS TEST MESSAGE - THIS SHOULD APPEAR IN THE CONSOLE');
            console.log('CHART MODIFICATION TEST - USING MODIFIED CHART');
            const categoryGroupCtx = document.getElementById('categoryGroupChart').getContext('2d');

            // Check if we have the combined visualization data
            const categoryGroupData = {{
                labels: {json.dumps(list(time_by_category.keys()))},
                datasets: []
            }};

            console.log('CUSTOM CHART: Using enhanced category-group chart with proper stacking');

            // Get the settings to understand category-group relationships
            const categorySettings = {json.dumps(settings.get('categories', []))};

            // Create a mapping of groups to their categories
            const groupToCategory = {{}};
            categorySettings.forEach(cat => {{
                const catName = cat.name;
                cat.groups.forEach(group => {{
                    // Handle both string and object formats
                    const groupName = typeof group === 'string' ? group : group.name;
                    groupToCategory[groupName] = catName;
                    // Also add lowercase version for case-insensitive matching
                    groupToCategory[groupName.toLowerCase()] = catName;
                }});
            }});

            // Add specific mappings for problematic groups
            // These will override any existing mappings
            const specificMappings = {{
                'Deep Learning Specialization': 'Training',
                'DeepLearning': 'Training',
                'NLP Course': 'Training',
                'AI News': 'Research',
                'AI-News': 'Research',
                'ActivityReports': 'Coding',
                'Work': 'Work&Finance'
            }};

            // Force these categories to exist even if they're not in the data
            const requiredCategories = ['Training', 'Research', 'Coding', 'Work&Finance', 'Other'];
            requiredCategories.forEach(cat => {{
                if (!time_by_category[cat]) {{
                    time_by_category[cat] = 0;
                    console.log(`Added missing category: ${cat}`);
                }}
            }});

            // Add the specific mappings to the groupToCategory object
            Object.entries(specificMappings).forEach(([group, category]) => {{
                groupToCategory[group] = category;
                // Also add lowercase version
                groupToCategory[group.toLowerCase()] = category;
                console.log(`Added specific mapping: ${group} -> ${category}`);
            }});

            console.log('CUSTOM CHART: Enhanced group-to-category mapping with fuzzy matching');

            // Helper function to normalize group names
            function normalizeGroupName(name) {{
                if (!name) return '';
                // Remove special characters and extra spaces
                return name.toString().replace(/[^\w\s]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
            }}

            // Create a mapping of normalized group names to original group names
            const normalizedToOriginal = {{}};
            Object.keys(groupToCategory).forEach(groupName => {{
                const normalized = normalizeGroupName(groupName);
                normalizedToOriginal[normalized] = groupName;
            }});

            // Helper function to calculate string similarity
            function stringSimilarity(s1, s2) {{
                if (!s1 || !s2) return 0;
                const longer = s1.length > s2.length ? s1 : s2;
                const shorter = s1.length > s2.length ? s2 : s1;
                const longerLength = longer.length;
                if (longerLength === 0) return 1.0;
                return (longerLength - editDistance(longer, shorter)) / parseFloat(longerLength);
            }}

            function editDistance(s1, s2) {{
                s1 = s1.toLowerCase();
                s2 = s2.toLowerCase();
                const costs = [];
                for (let i = 0; i <= s1.length; i++) {{
                    let lastValue = i;
                    for (let j = 0; j <= s2.length; j++) {{
                        if (i === 0) costs[j] = j;
                        else if (j > 0) {{
                            let newValue = costs[j - 1];
                            if (s1.charAt(i - 1) !== s2.charAt(j - 1))
                                newValue = Math.min(Math.min(newValue, lastValue), costs[j]) + 1;
                            costs[j - 1] = lastValue;
                            lastValue = newValue;
                        }}
                    }}
                    if (i > 0) costs[s2.length] = lastValue;
                }}
                return costs[s2.length];
            }}

            // Process each group in time_by_group
            const groupsByCategory = {{}};

            // Initialize categories
            Object.keys(time_by_category).forEach(cat => {{
                groupsByCategory[cat] = [];
            }});

            // Add 'Other' category if not present
            if (!groupsByCategory['Other']) {{
                groupsByCategory['Other'] = [];
            }}

            // Assign groups to categories with enhanced matching
            Object.entries(time_by_group).forEach(([group, time]) => {{
                // Try different matching strategies
                let category = null;

                // 1. Try exact match
                if (groupToCategory[group]) {{
                    category = groupToCategory[group];
                    console.log(`Found exact match for group '${group}' -> '${category}'`);
                }}
                // 2. Try lowercase match
                else if (groupToCategory[group.toLowerCase()]) {{
                    category = groupToCategory[group.toLowerCase()];
                    console.log(`Found lowercase match for group '${group}' -> '${category}'`);
                }}
                // 3. Try normalized match
                else {{
                    const normalizedGroup = normalizeGroupName(group);
                    if (normalizedToOriginal[normalizedGroup]) {{
                        const originalGroup = normalizedToOriginal[normalizedGroup];
                        category = groupToCategory[originalGroup];
                        console.log(`Found normalized match for group '${group}' -> '${originalGroup}' -> '${category}'`);
                    }}
                    // 4. Try fuzzy matching
                    else {{
                        // Find the best match among all normalized group names
                        let bestMatch = null;
                        let bestScore = 0.7; // Threshold for similarity

                        Object.entries(normalizedToOriginal).forEach(([normName, origName]) => {{
                            // Skip very short names to avoid false matches
                            if (normName.length < 3 || normalizedGroup.length < 3) return;

                            // Calculate similarity
                            const similarity = stringSimilarity(normalizedGroup, normName);

                            // Check if this is a substring match
                            const substringMatch = normName.includes(normalizedGroup) || normalizedGroup.includes(normName);
                            const adjustedSimilarity = substringMatch ? Math.max(similarity, 0.8) : similarity;

                            if (adjustedSimilarity > bestScore) {{
                                bestMatch = origName;
                                bestScore = adjustedSimilarity;
                            }}
                        }});

                        if (bestMatch) {{
                            category = groupToCategory[bestMatch];
                            console.log(`Found fuzzy match for group '${group}' -> '${bestMatch}' (score: ${bestScore.toFixed(2)}) -> '${category}'`);
                        }}
                    }}
                }}

                // If no match found, use 'Other'
                if (!category) {{
                    category = 'Other';
                    console.log(`No category match found for group '${group}', assigning to 'Other'`);
                }}

                // Add to the appropriate category
                if (!groupsByCategory[category]) {{
                    groupsByCategory[category] = [];
                }}

                groupsByCategory[category].push({{ name: group, time }});
            }});

            // Get all unique groups
            const allGroups = Object.keys(time_by_group);
            const groupColors = getDistinctColors(allGroups.length);

            // Create a color map for groups
            const groupColorMap = {{}};
            allGroups.forEach((group, index) => {{
                groupColorMap[group] = groupColors[index];
            }});

            // For each category, create datasets for each group
            const categoryLabels = Object.keys(time_by_category);

            categoryLabels.forEach(category => {{
                const categoryGroups = groupsByCategory[category] || [];

                // Sort groups by time (descending)
                categoryGroups.sort((a, b) => b.time - a.time);

                // Add each group as a separate dataset
                categoryGroups.forEach(groupInfo => {{
                    const groupName = groupInfo.name;
                    const groupTime = groupInfo.time;

                    // Create data array with zeros for all categories except this one
                    const data = Array(categoryLabels.length).fill(0);
                    const categoryIndex = categoryLabels.indexOf(category);
                    // Keep the data in minutes for now - the y-axis ticks will convert to hours
                    data[categoryIndex] = groupTime;
                    console.log(`Adding ${groupTime} minutes (${(groupTime/60).toFixed(1)}h) for ${groupName} in ${category}`);

                    categoryGroupData.datasets.push({{
                        label: `${{category}} - ${{groupName}}`,
                        data: data,
                        backgroundColor: groupColorMap[groupName] || 'rgba(200, 200, 200, 0.7)',
                        borderColor: (groupColorMap[groupName] || 'rgba(200, 200, 200, 0.7)').replace('0.7', '1'),
                        borderWidth: 1,
                        stack: category  // Stack bars by category
                    }});
                }});
            }});

            const categoryGroupChart = new Chart(categoryGroupCtx, {{
                type: 'bar',
                data: categoryGroupData,
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        title: {{
                            display: true,
                            text: 'MODIFIED CHART - Category-Group Distribution',
                            font: {{
                                size: 24,
                                weight: 'bold'
                            }}
                        }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    const value = context.raw;
                                    // Convert minutes to hours with 1 decimal place
                                    const hours = (value / 60).toFixed(1);
                                    return `${{context.dataset.label}}: ${{hours}}h`;
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            title: {{
                                display: true,
                                text: 'Categories'
                            }}
                        }},
                        y: {{
                            stacked: true,
                            title: {{
                                display: true,
                                text: 'Hours'
                            }},
                            ticks: {{
                                callback: function(value, index, values) {{
                                    // Convert minutes to hours with 1 decimal place
                                    return (value / 60).toFixed(1) + 'h';
                                }}
                            }}
                        }}
                    }}
                }}
            }});

            // Create doughnut chart for category distribution
            const doughnutCtx = document.getElementById('categoryGroupDoughnut').getContext('2d');
            const doughnutChart = new Chart(doughnutCtx, {{
                type: 'doughnut',
                data: {{
                    labels: categoryLabels,
                    datasets: [{{
                        data: categoryValues,
                        backgroundColor: categoryColors,
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        title: {{
                            display: true,
                            text: 'Activity Distribution by Category',
                            font: {{
                                size: 16
                            }}
                        }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    const value = context.raw;
                                    const hours = Math.floor(value / 60);
                                    const minutes = value % 60;
                                    return `${{context.label}}: ${{hours}}h ${{minutes}}m`;
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """

    return html

def update_weekly_report(report_path):
    """
    Update a weekly report with enhanced visualizations.

    Args:
        report_path: Path to the report file

    Returns:
        True if successful, False otherwise
    """
    try:
        # Read the report file
        with open(report_path, 'r') as f:
            report_data = json.load(f)

        # Generate an enhanced HTML report
        html_report = generate_enhanced_html_report(report_data)

        # Update the report data
        report_data['html_report'] = html_report

        # Save the updated report
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"Successfully updated weekly report with enhanced visualizations: {report_path}")
        return True

    except Exception as e:
        logger.error(f"Error updating report {report_path}: {e}")
        return False

def update_all_weekly_reports():
    """Update all weekly reports with enhanced visualizations."""
    # Create the directory if it doesn't exist
    os.makedirs(WEEKLY_REPORTS_DIR, exist_ok=True)

    # Get all weekly report files
    report_files = list(WEEKLY_REPORTS_DIR.glob("weekly_report_*.json"))
    logger.info(f"Found {len(report_files)} weekly report files")

    success_count = 0
    for report_file in report_files:
        if update_weekly_report(report_file):
            success_count += 1

    logger.info(f"Successfully updated {success_count} out of {len(report_files)} weekly reports")

if __name__ == "__main__":
    update_all_weekly_reports()
