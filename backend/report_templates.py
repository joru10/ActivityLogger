import json
import logging
from datetime import date
from pydantic import BaseModel

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DailyTimeBreakdown(BaseModel):
    total_time: int
    time_by_group: dict[str, int]
    time_by_category: dict[str, int] = {}

class ChartData(BaseModel):
    chart_type: str  # 'bar', 'pie', 'line', etc.
    labels: list[str]
    datasets: list[dict]
    title: str
    description: str = ""

def generate_html_report(start_date: date, end_date: date, total_time: int, time_by_group: dict, 
                         time_by_category: dict, daily_breakdown: dict, visualizations: dict, 
                         logs_data: list[dict]) -> str:
    """Generates an HTML report with embedded Chart.js visualizations.
    
    Args:
        start_date: Start date of the report period
        end_date: End date of the report period
        total_time: Total time spent on activities in minutes
        time_by_group: Dictionary mapping groups to total time spent
        time_by_category: Dictionary mapping categories to total time spent
        daily_breakdown: Dictionary mapping dates to DailyTimeBreakdown objects
        visualizations: Dictionary mapping visualization names to ChartData objects
        logs_data: List of activity log dictionaries
        
    Returns:
        HTML string containing the report with embedded charts
    """
    
    # Create a meaningful summary based on the data
    def generate_meaningful_summary(total_time, time_by_group, time_by_category, daily_breakdown):
        if not time_by_group and not time_by_category:
            return "No activities recorded for this period."
            
        # Find the most active day
        most_active_day = None
        most_active_time = 0
        for day, data in daily_breakdown.items():
            if data.total_time > most_active_time:
                most_active_time = data.total_time
                most_active_day = day
                
        # Find the top groups and categories
        top_groups = sorted(time_by_group.items(), key=lambda x: x[1], reverse=True)[:3]
        top_categories = sorted(time_by_category.items(), key=lambda x: x[1], reverse=True)[:3]
        
        # Build the summary
        summary_parts = []
        
        # Add total time info
        hours = total_time // 60
        minutes = total_time % 60
        summary_parts.append(f"You spent a total of {hours} hours and {minutes} minutes on {len(logs_data)} activities.")
        
        # Add most active day if available
        if most_active_day:
            try:
                day_date = date.fromisoformat(most_active_day)
                formatted_day = day_date.strftime("%A, %B %d")
            except ValueError:
                formatted_day = most_active_day
                
            most_active_hours = most_active_time // 60
            most_active_minutes = most_active_time % 60
            summary_parts.append(f"Your most active day was {formatted_day} with {most_active_hours} hours and {most_active_minutes} minutes.")
        
        # Add top groups if available
        if top_groups:
            group_parts = []
            for group, time in top_groups:
                hours = time // 60
                minutes = time % 60
                group_parts.append(f"{group} ({hours}h {minutes}m)")
            summary_parts.append(f"Most time was spent on: {', '.join(group_parts)}.")
        
        # Add top categories if available
        if top_categories:
            category_parts = []
            for category, time in top_categories:
                hours = time // 60
                minutes = time % 60
                category_parts.append(f"{category} ({hours}h {minutes}m)")
            summary_parts.append(f"Top categories: {', '.join(category_parts)}.")
            
        return " ".join(summary_parts)
    # Generate a meaningful summary
    meaningful_summary = generate_meaningful_summary(total_time, time_by_group, time_by_category, daily_breakdown)
    
    logger.info("Generating HTML report with visualizations")
    
    # Create default visualizations if none are provided
    if not visualizations:
        visualizations = {}
        
        # 1. Daily Activity Distribution (Bar Chart)
        if daily_breakdown:
            days = sorted(daily_breakdown.keys())
            daily_times = [daily_breakdown[day].total_time for day in days]
            
            # Format days for display (e.g., "Mon, Mar 3")
            formatted_days = []
            for day_str in days:
                try:
                    day_date = date.fromisoformat(day_str)
                    formatted_days.append(day_date.strftime("%a, %b %d"))
                except ValueError:
                    formatted_days.append(day_str)
            
            visualizations["daily_activity"] = ChartData(
                chart_type="bar",
                title="Daily Activity Distribution",
                description="Time spent on activities each day of the week",
                labels=formatted_days,
                datasets=[{
                    "label": "Minutes",
                    "data": daily_times,
                    "backgroundColor": "rgba(54, 162, 235, 0.5)",
                    "borderColor": "rgba(54, 162, 235, 1)",
                    "borderWidth": 1
                }]
            )
        
        # 2. Combined Category-Group Chart (Stacked Bar Chart)
        if time_by_category and time_by_group:
            # Get categories and their times
            categories = list(time_by_category.keys())
            category_times = list(time_by_category.values())
            
            # Get settings to understand the category-group relationship
            import sqlite3
            try:
                # Connect to the database
                conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend', 'activity_logs.db'))
                cursor = conn.cursor()
                
                # Get the categories configuration
                cursor.execute('SELECT categories FROM settings LIMIT 1')
                result = cursor.fetchone()
                if result and result[0]:
                    categories_config = json.loads(result[0])
                else:
                    categories_config = []
                conn.close()
            except Exception as e:
                logger.error(f"Error fetching categories from database: {e}")
                categories_config = []
            
            # Create a mapping of groups to their categories
            group_to_category = {}
            for cat_config in categories_config:
                cat_name = cat_config.get('name', '')
                for group_name in cat_config.get('groups', []):
                    group_to_category[group_name] = cat_name
            
            # Organize groups by category
            groups_by_category = {}
            for group, time in time_by_group.items():
                category = group_to_category.get(group, 'Other')
                if category not in groups_by_category:
                    groups_by_category[category] = []
                groups_by_category[category].append({'name': group, 'time': time})
            
            # Generate colors for categories (more distinct colors)
            import colorsys
            def get_distinct_colors(n):
                colors = []
                for i in range(n):
                    hue = i / n
                    saturation = 0.7
                    value = 0.9
                    rgb = colorsys.hsv_to_rgb(hue, saturation, value)
                    rgba = f"rgba({int(rgb[0] * 255)}, {int(rgb[1] * 255)}, {int(rgb[2] * 255)}, 0.7)"
                    colors.append(rgba)
                return colors
            
            category_colors = get_distinct_colors(len(categories))
            
            # Create a stacked bar chart dataset where each group is a separate dataset
            datasets = []
            
            # Get all unique groups across all categories
            all_groups = set()
            for groups in groups_by_category.values():
                for group_info in groups:
                    all_groups.add(group_info['name'])
            all_groups = sorted(list(all_groups))
            
            # Create a color for each group - using more vibrant colors
            def get_vibrant_colors(n):
                colors = []
                base_colors = [
                    "rgba(255, 99, 132, 0.7)",   # Red
                    "rgba(54, 162, 235, 0.7)",  # Blue
                    "rgba(255, 206, 86, 0.7)",  # Yellow
                    "rgba(75, 192, 192, 0.7)",  # Teal
                    "rgba(153, 102, 255, 0.7)", # Purple
                    "rgba(255, 159, 64, 0.7)",  # Orange
                    "rgba(46, 204, 113, 0.7)",  # Green
                    "rgba(142, 68, 173, 0.7)",  # Violet
                    "rgba(241, 196, 15, 0.7)",  # Amber
                    "rgba(231, 76, 60, 0.7)",   # Crimson
                    "rgba(52, 152, 219, 0.7)",  # Dodger Blue
                    "rgba(155, 89, 182, 0.7)"   # Amethyst
                ]
                
                # Use base colors first
                for i in range(min(n, len(base_colors))):
                    colors.append(base_colors[i])
                
                # If we need more colors, generate them
                if n > len(base_colors):
                    for i in range(len(base_colors), n):
                        hue = i / n
                        saturation = 0.85
                        value = 0.9
                        rgb = colorsys.hsv_to_rgb(hue, saturation, value)
                        rgba = f"rgba({int(rgb[0] * 255)}, {int(rgb[1] * 255)}, {int(rgb[2] * 255)}, 0.7)"
                        colors.append(rgba)
                return colors
            
            group_colors = get_vibrant_colors(len(all_groups))
            group_color_map = {group: color for group, color in zip(all_groups, group_colors)}
            
            # For each category, create datasets for each of its groups
            for category in categories:
                # Get all groups for this category
                category_groups = groups_by_category.get(category, [])
                
                # Sort groups by time (descending)
                category_groups.sort(key=lambda x: x['time'], reverse=True)
                
                # Add each group as a separate dataset
                for group_info in category_groups:
                    group_name = group_info['name']
                    group_time = group_info['time']
                    
                    # Create data array with zeros for all categories except this one
                    data = [0] * len(categories)
                    category_index = categories.index(category)
                    data[category_index] = group_time
                    
                    datasets.append({
                        "label": f"{category} - {group_name}",
                        "data": data,
                        "backgroundColor": group_color_map.get(group_name, "rgba(200, 200, 200, 0.7)"),
                        "borderColor": group_color_map.get(group_name, "rgba(200, 200, 200, 1)").replace('0.7', '1'),
                        "borderWidth": 1,
                        "stack": category  # Stack bars by category
                    })
            
            visualizations["category_group_distribution"] = ChartData(
                chart_type="bar",
                title="Activity Distribution by Category and Group",
                description="Breakdown of time spent on different categories and their groups",
                labels=categories,  # Each category gets its own bar
                datasets=datasets
            )
            
            # Also create a doughnut chart that shows categories and groups
            # This provides a hierarchical view with categories as the outer ring
            # and groups as the inner ring
            visualizations["category_group_doughnut"] = ChartData(
                chart_type="doughnut",
                title="Hierarchical Activity Distribution",
                description="Breakdown of time spent by category (outer ring) and group (inner ring)",
                labels=categories,
                datasets=[{
                    "data": category_times,
                    "backgroundColor": category_colors,
                    "borderWidth": 1
                }]
            )
    
    logger.info(f"Created {len(visualizations)} visualizations for the report")
    
    # Format dates for display
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    # Convert minutes to hours and minutes for display
    hours = total_time // 60
    minutes = total_time % 60
    time_display = f"{hours} hours, {minutes} minutes"
    
    # Create HTML header with Chart.js library and jQuery for better compatibility
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Weekly Activity Report: {start_date_str} to {end_date_str}</title>
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; }}
            h1, h2, h3 {{ color: #2c3e50; }}
            .report-header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
            .summary-box {{ background-color: #e9ecef; padding: 15px; border-radius: 5px; margin-bottom: 15px; }}
            .chart-container {{ display: flex; flex-wrap: wrap; justify-content: space-between; margin-bottom: 30px; }}
            .chart-item {{ width: 48%; margin-bottom: 20px; background-color: #fff; border-radius: 5px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            .daily-breakdown {{ margin-top: 30px; }}
            .daily-item {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 15px; }}
            .activity-log {{ margin-top: 30px; }}
            table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f8f9fa; }}
            tr:hover {{ background-color: #f5f5f5; }}
            @media (max-width: 768px) {{ .chart-item {{ width: 100%; }} }}
        </style>
    </head>
    <body>
        <div class="report-header">
            <h1>Weekly Activity Report</h1>
            <h2>{start_date_str} to {end_date_str}</h2>
        </div>
    """
    
    # Executive Summary Section with meaningful summary
    html += f"""
        <section>
            <h2>Executive Summary</h2>
            <div class="summary-box">
                <p>{meaningful_summary}</p>
            </div>
        </section>
    """
    
    # Weekly Totals Section
    html += """
        <section>
            <h2>Weekly Totals</h2>
            <table class="totals-table">
                <thead>
                    <tr>
                        <th>Group</th>
                        <th>Category</th>
                        <th>Time</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    # Generate combined group/category data for the totals table
    combined_data = {}
    for log in logs_data:
        group = log.get("group", "Other")
        category = log.get("category", "Other")
        duration = log["duration_minutes"]
        
        key = (group, category)
        if key not in combined_data:
            combined_data[key] = 0
        combined_data[key] += duration
    
    # Sort by group then by time spent
    sorted_combined = sorted(combined_data.items(), key=lambda x: (x[0][0], -x[1]))
    
    # Add rows to the totals table
    for (group, category), time in sorted_combined:
        hours = time // 60
        minutes = time % 60
        time_display = f"{hours}h {minutes}m"
        
        html += f"""
                    <tr>
                        <td>{group}</td>
                        <td>{category}</td>
                        <td>{time_display}</td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
            </div>
        </section>
    """
    
    # Visualizations Section
    html += """
        <section>
            <h2>Visualizations</h2>
    """
    
    # Generate chart containers and scripts for each visualization
    chart_scripts = []
    for i, (chart_id, chart_data) in enumerate(visualizations.items()):
        # Create a unique canvas ID for each chart
        canvas_id = f"chart_{chart_id}"
        
        # Add chart container with data table
        html += f"""
            <div class="chart-container">
                <div class="chart-item">
                    <h3>{chart_data.title}</h3>
                    <p>{chart_data.description}</p>
                    <div style="position: relative; height: 300px;">
                        <canvas id="{canvas_id}"></canvas>
                    </div>
                </div>
                <div class="chart-data">
                    <h3>Data</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>{chart_id.replace('_', ' ').title()}</th>
                                <th>Time</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        
        # Add data rows for the chart data table
        if chart_id == "daily_activity":
            # For daily activity chart, show the time for each day
            for i, label in enumerate(chart_data.labels):
                time_value = chart_data.datasets[0]["data"][i]
                hours = time_value // 60
                minutes = time_value % 60
                time_display = f"{hours}h {minutes}m"
                
                html += f"""
                                <tr>
                                    <td>{label}</td>
                                    <td>{time_display}</td>
                                </tr>
                """
        else:
            # For other charts (group/category distribution)
            for i, label in enumerate(chart_data.labels):
                time_value = chart_data.datasets[0]["data"][i]
                hours = time_value // 60
                minutes = time_value % 60
                time_display = f"{hours}h {minutes}m"
                
                html += f"""
                                <tr>
                                    <td>{label}</td>
                                    <td>{time_display}</td>
                                </tr>
                """
                
        html += """
                        </tbody>
                    </table>
                </div>
            </div>
        """
        
        # Add data rows for the chart data table
        if chart_id == "daily_activity":
            # For daily activity chart, show the time for each day
            for i, label in enumerate(chart_data.labels):
                time_value = chart_data.datasets[0]["data"][i]
                hours = time_value // 60
                minutes = time_value % 60
                time_display = f"{hours}h {minutes}m"
                
                html += f"""
                                <tr>
                                    <td style="padding: 8px; text-align: left; border-bottom: 1px solid #ddd;">{label}</td>
                                    <td style="padding: 8px; text-align: left; border-bottom: 1px solid #ddd;">{time_display}</td>
                                </tr>
                """
        else:
            # For other charts (group/category distribution)
            for i, label in enumerate(chart_data.labels):
                time_value = chart_data.datasets[0]["data"][i]
                hours = time_value // 60
                minutes = time_value % 60
                time_display = f"{hours}h {minutes}m"
                
                html += f"""
                                <tr>
                                    <td style="padding: 8px; text-align: left; border-bottom: 1px solid #ddd;">{label}</td>
                                    <td style="padding: 8px; text-align: left; border-bottom: 1px solid #ddd;">{time_display}</td>
                                </tr>
                """
                
        html += """
                        </tbody>
                    </table>
                </div>
            </div>
        """
        
        # Prepare chart script with more detailed configuration
        labels_json = json.dumps(chart_data.labels)
        datasets_json = json.dumps(chart_data.datasets)
        
        # Configure chart options based on chart type
        chart_options = {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {
                "legend": {
                    "position": "top",
                    "labels": {
                        "font": {
                            "size": 12
                        }
                    }
                },
                "title": {
                    "display": True,
                    "text": chart_data.title,
                    "font": {
                        "size": 16
                    }
                },
                "tooltip": {
                    "enabled": True,
                    "callbacks": {
                        "label": "function(context) {\n"
                                "                const value = context.raw;\n"
                                "                const hours = Math.floor(value / 60);\n"
                                "                const minutes = value % 60;\n"
                                "                return `${context.dataset.label}: ${hours}h ${minutes}m`;\n"
                                "            }"
                    }
                }
            }
        }
        
        # Add specific options for bar charts
        if chart_data.chart_type == 'bar':
            # Check if this is the combined category-group chart
            is_stacked = any('stack' in dataset for dataset in chart_data.datasets)
            if is_stacked or chart_id == 'category_group_chart' or chart_id == 'category_group_distribution':
                chart_options["scales"] = {
                    "x": {
                        "stacked": True,
                        "title": {
                            "display": True,
                            "text": "Categories"
                        }
                    },
                    "y": {
                        "stacked": True,
                        "title": {
                            "display": True,
                            "text": "Minutes"
                        }
                    }
                }
                
                # Add better legend configuration for stacked charts
                chart_options["plugins"]["legend"] = {
                    "position": "right",
                    "labels": {
                        "font": {
                            "size": 10
                        },
                        "boxWidth": 12
                    }
                }
        
        # Convert options to JSON
        options_json = json.dumps(chart_options)
        
        chart_script = f"""
        (function() {{
            const ctx = document.getElementById('{canvas_id}').getContext('2d');
            const config = {{
                type: '{chart_data.chart_type}',
                data: {{
                    labels: {labels_json},
                    datasets: {datasets_json}
                }},
                options: {options_json}
            }};
            new Chart(ctx, config);
        }})();
        """
        chart_scripts.append(chart_script)
    
    html += """
            </div>
        </section>
    """
    
    # Daily Breakdown Section with smaller font
    html += """
        <section class="daily-breakdown">
            <h2>Daily Details</h2>
            <div style="font-size: 0.9em;">
    """
    
    # Sort days chronologically
    sorted_days = sorted(daily_breakdown.keys())
    
    for day in sorted_days:
        day_data = daily_breakdown[day]
        day_hours = day_data.total_time // 60
        day_minutes = day_data.total_time % 60
        day_time_display = f"{day_hours} hours, {day_minutes} minutes"
        
        # Format the groups and categories for display
        groups_html = ""
        for group, time in day_data.time_by_group.items():
            group_hours = time // 60
            group_minutes = time % 60
            groups_html += f"<li><strong>{group}:</strong> {group_hours}h {group_minutes}m</li>"
        
        categories_html = ""
        for category, time in day_data.time_by_category.items():
            category_hours = time // 60
            category_minutes = time % 60
            categories_html += f"<li><strong>{category}:</strong> {category_hours}h {category_minutes}m</li>"
        
        html += f"""
            <div class="daily-item">
                <h3>{day}</h3>
                <p><strong>Total Time:</strong> {day_time_display}</p>
                
                <div style="display: flex; flex-wrap: wrap;">
                    <div style="flex: 1; min-width: 300px;">
                        <h4>Time by Group</h4>
                        <ul>
                            {groups_html}
                        </ul>
                    </div>
                    <div style="flex: 1; min-width: 300px;">
                        <h4>Time by Category</h4>
                        <ul>
                            {categories_html}
                        </ul>
                    </div>
                </div>
            </div>
        """
    
    html += """
            </div>
        </section>
    """
    
    # Detailed Activity Log Section with smaller font
    html += """
        <section class="activity-log">
            <h2>Detailed Activity Log</h2>
            <div style="font-size: 0.9em;">
            <table>
                <thead>
                    <tr>
                        <th>Date & Time</th>
                        <th>Group</th>
                        <th>Category</th>
                        <th>Duration</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    # Sort logs by timestamp
    sorted_logs = sorted(logs_data, key=lambda x: x["timestamp"])
    
    for log in sorted_logs:
        timestamp = log["timestamp"]
        group = log.get("group", "Other")
        category = log.get("category", "Other")
        duration = log["duration_minutes"]
        description = log.get("description", "")
        
        # Format duration as hours and minutes
        duration_hours = duration // 60
        duration_minutes = duration % 60
        if duration_hours > 0:
            duration_display = f"{duration_hours}h {duration_minutes}m"
        else:
            duration_display = f"{duration_minutes}m"
        
        html += f"""
                    <tr>
                        <td>{timestamp}</td>
                        <td>{group}</td>
                        <td>{category}</td>
                        <td>{duration_display}</td>
                        <td>{description}</td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
            </div>
        </section>
    """
    
    # Add scripts and close HTML tags
    html += """
        <script>
            $(document).ready(function() {
    """
    
    # Add all chart scripts
    for script in chart_scripts:
        html += script
    
    html += """
            });
        </script>
        
        <!-- Inline script for debugging -->
        <script>
            console.log('Report loaded, initializing charts...');
            // Check if Chart.js is loaded
            if (typeof Chart !== 'undefined') {
                console.log('Chart.js is loaded properly');
            } else {
                console.error('Chart.js is not loaded!');
            }
            
            // Check if canvas elements exist
            $(document).ready(function() {
                $('canvas').each(function() {
                    console.log('Found canvas with ID: ' + $(this).attr('id'));
                });
                
                if ($('canvas').length === 0) {
                    console.error('No canvas elements found!');
                }
            });
        </script>
    </body>
    </html>
    """
    
    logger.info("HTML report generation complete")
    return html
