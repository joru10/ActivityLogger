import json
import logging
from datetime import date
from pydantic import BaseModel

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DailyTimeBreakdown(BaseModel):
    total_time: float
    time_by_group: dict[str, float]
    time_by_category: dict[str, float] = {}

class ChartData(BaseModel):
    chart_type: str  # 'bar', 'pie', 'line', etc.
    labels: list[str]
    datasets: list[dict]
    title: str
    description: str = ""
    options: dict = {}

def generate_html_report(start_date: date, end_date: date, total_time: float, time_by_group: dict,
                         time_by_category: dict, daily_breakdown: dict, visualizations: dict,
                         logs_data: list[dict]) -> str:
    # Add a very obvious debug message to confirm this function is being called
    logger.error("*******************************************************************************")
    logger.error("* GENERATING HTML REPORT WITH NEW CODE - THIS SHOULD APPEAR IN THE LOGS *")
    logger.error("*******************************************************************************")
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
            daily_times_minutes = [daily_breakdown[day].total_time for day in days]

            # Convert minutes to hours with 1 decimal place - FORCE conversion
            daily_times_hours = []
            for time_in_minutes in daily_times_minutes:
                try:
                    time_in_minutes = float(time_in_minutes)
                    time_in_hours = round(time_in_minutes / 60.0, 1)
                    daily_times_hours.append(time_in_hours)
                    logger.debug(f"Converted daily time {time_in_minutes} minutes to {time_in_hours} hours")
                except (ValueError, TypeError) as e:
                    logger.error(f"Error converting daily time value: {time_in_minutes}, error: {e}")
                    daily_times_hours.append(0.0)

            # Format days for display (e.g., "Mon, Mar 3")
            formatted_days = []
            for day_str in days:
                try:
                    day_date = date.fromisoformat(day_str)
                    formatted_days.append(day_date.strftime("%a, %b %d"))
                except ValueError:
                    formatted_days.append(day_str)

            # Log the daily times for debugging
            logger.info(f"Daily times (in hours): {list(zip(formatted_days, daily_times_hours))}")

            visualizations["daily_activity"] = ChartData(
                chart_type="bar",
                title="Daily Activity Distribution",
                description="Time spent on activities each day of the week",
                labels=formatted_days,
                datasets=[{
                    "label": "Hours",
                    "data": daily_times_hours,  # Already converted to hours
                    "backgroundColor": "rgba(54, 162, 235, 0.5)",
                    "borderColor": "rgba(54, 162, 235, 1)",
                    "borderWidth": 1
                }],
                options={
                    "scales": {
                        "y": {
                            "title": {
                                "display": True,
                                "text": "Hours"
                            },
                            "ticks": {
                                "callback": "function(value) { return value.toFixed(1) + 'h'; }"
                            }
                        }
                    }
                }
            )

        # 2. Category Distribution Chart (Pie Chart)
        if time_by_category and time_by_group:
            # Import os for path operations
            import os
            import sqlite3
            from config import get_categories_json

            # Get categories configuration directly from the config function
            try:
                categories_json = get_categories_json()
                categories_config = json.loads(categories_json)
                logger.info(f"Successfully loaded categories config from get_categories_json()")
            except Exception as e:
                logger.error(f"Error loading categories from get_categories_json(): {e}")
                # Fallback to database if config function fails
                try:
                    # Connect to the database
                    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'activity_logs.db'))
                    cursor = conn.cursor()

                    # Get the categories configuration
                    cursor.execute('SELECT categories FROM settings LIMIT 1')
                    result = cursor.fetchone()
                    if result and result[0]:
                        categories_config = json.loads(result[0])
                        logger.info(f"Loaded categories config from database")
                    else:
                        categories_config = []
                        logger.warning("No categories found in database")
                    conn.close()
                except Exception as db_e:
                    logger.error(f"Error fetching categories from database: {db_e}")
                    categories_config = []

            # Ensure categories_config is a list
            if categories_config is None:
                categories_config = []
                logger.warning("Categories config is None, using empty list")
            elif not isinstance(categories_config, list):
                logger.warning(f"Categories config is not a list: {type(categories_config)}, converting to list")
                # If it's a dictionary, try to convert it to a list of dictionaries
                if isinstance(categories_config, dict):
                    categories_config = [categories_config]
                else:
                    # If it's something else, just use an empty list
                    categories_config = []

            # Log the loaded categories configuration for debugging
            logger.info(f"Categories config: {json.dumps(categories_config)[:500]}...")

            # Create a mapping of groups to their categories
            group_to_category = {}
            for cat_config in categories_config:
                # Check if cat_config is a dictionary
                if isinstance(cat_config, dict):
                    cat_name = cat_config.get('name', '')
                    groups = cat_config.get('groups', [])
                else:
                    # If cat_config is a string, use it as the category name
                    cat_name = str(cat_config)
                    groups = []
                    logger.warning(f"Category config is not a dictionary: {cat_config}")

                # Process groups for this category
                for group_item in groups:
                    # Handle both string and dictionary formats for groups
                    if isinstance(group_item, dict) and 'name' in group_item:
                        group_name = group_item['name']
                    else:
                        group_name = str(group_item)

                    # Add to mapping
                    group_to_category[group_name] = cat_name
                    # Also add lowercase version for case-insensitive matching
                    group_to_category[group_name.lower()] = cat_name

                    logger.info(f"Mapped group '{group_name}' to category '{cat_name}'")

            # Log the group-to-category mapping
            logger.info(f"Group to category mapping: {json.dumps(group_to_category)[:500]}...")

            # Organize groups by category
            groups_by_category = {
                'Training': [],
                'Research': [],
                'Coding': [],
                'Work&Finance': [],
                'Other': []
            }
            # Reset time_by_category to ensure it's calculated correctly based on the actual group-category relationships
            recalculated_time_by_category = {
                'Training': 0,
                'Research': 0,
                'Coding': 0,
                'Work&Finance': 0,
                'Other': 0
            }

            # First, initialize all categories from the config to ensure they all appear in the chart
            for cat_config in categories_config:
                # Check if cat_config is a dictionary
                if isinstance(cat_config, dict):
                    cat_name = cat_config.get('name', '')
                else:
                    # If cat_config is a string, use it as the category name
                    cat_name = str(cat_config)
                    logger.warning(f"Category config is not a dictionary: {cat_config}")

                if cat_name:
                    groups_by_category[cat_name] = []
                    recalculated_time_by_category[cat_name] = 0

            # Add an 'Other' category for groups that don't match any configured category
            if 'Other' not in groups_by_category:
                groups_by_category['Other'] = []
                recalculated_time_by_category['Other'] = 0

            # Helper function to normalize group names for better matching
            def normalize_group_name(name):
                """Normalize group name by removing special characters and standardizing format."""
                if not name:
                    return ""
                # Convert to string
                name = str(name)
                # Remove special characters and extra spaces
                import re
                name = re.sub(r'[^\w\s]', '', name)
                # Replace multiple spaces with a single space
                name = re.sub(r'\s+', ' ', name)
                # Trim and lowercase
                return name.strip().lower()

            # Helper function to calculate similarity between two strings
            def string_similarity(s1, s2):
                """Calculate similarity ratio between two strings."""
                from difflib import SequenceMatcher
                return SequenceMatcher(None, s1, s2).ratio()

            # Create a mapping of normalized group names to original group names
            normalized_to_original = {}
            for group_name in group_to_category.keys():
                if isinstance(group_name, str):
                    normalized = normalize_group_name(group_name)
                    normalized_to_original[normalized] = group_name

            # Define specific group-to-category mappings
            specific_mappings = {
                'Deep Learning Specialization': 'Training',
                'DeepLearning': 'Training',
                'NLP Course': 'Training',
                'AI News': 'Research',
                'AI-News': 'Research',
                'Papers': 'Research',
                'Articles': 'Research',
                'Videos': 'Research',
                'ActivityReports': 'Coding',
                'Tools': 'Coding',
                'tools': 'Coding',
                'Colabs': 'Coding',
                'MultiAgent': 'Coding',
                'EdgeTabs': 'Coding',
                'MediaConversion': 'Coding',
                'OneNoteRAG': 'Coding',
                'Work': 'Work&Finance',
                'Unemployment': 'Work&Finance',
                'Pensions': 'Work&Finance',
                'taxes': 'Work&Finance'
            }

            # Process each group and assign it to the correct category
            for group, time in time_by_group.items():
                # Try to find the category for this group with different matching strategies
                category = None

                # 1. Check specific mappings first
                if group in specific_mappings:
                    category = specific_mappings[group]
                    logger.info(f"Using specific mapping for group '{group}' -> '{category}'")
                # 2. Check if the group name is the same as a category name (case-insensitive)
                elif any(cat.lower() == group.lower() for cat in ['Training', 'Research', 'Coding', 'Work&Finance', 'Business']):
                    # Find which category matches
                    for cat in ['Training', 'Research', 'Coding', 'Work&Finance', 'Business']:
                        if cat.lower() == group.lower():
                            category = cat
                            logger.info(f"Group name '{group}' matches category name '{category}', assigning to that category")
                            break
                # 3. Try exact match with group_to_category
                elif group in group_to_category:
                    category = group_to_category[group]
                    logger.info(f"Found exact match for group '{group}' -> '{category}'")
                # 4. Try lowercase match
                elif group.lower() in group_to_category:
                    category = group_to_category[group.lower()]
                    logger.info(f"Found lowercase match for group '{group}' -> '{category}'")
                # 5. Check for common misspellings or variants
                elif any(variant in group.lower() for variant in ['ai news', 'aa news', 'ai-news', 'ai_news']):
                    category = 'Research'
                    logger.info(f"Group '{group}' appears to be a variant of 'AI News', assigning to Research category")
                # 6. Try normalized match
                elif normalize_group_name(group) in normalized_to_original:
                    original = normalized_to_original[normalize_group_name(group)]
                    category = group_to_category[original]
                    logger.info(f"Found normalized match for group '{group}' -> '{original}' -> '{category}'")
                # 7. Try fuzzy matching with specific mappings
                else:
                    # Try to match with specific mappings first
                    for known_group, cat in specific_mappings.items():
                        if group.lower() in known_group.lower() or known_group.lower() in group.lower():
                            category = cat
                            logger.info(f"Found similar group in specific mappings '{known_group}' for '{group}', assigning to '{cat}'")
                            break

                        # If no match found in specific mappings, try fuzzy matching with all groups
                        if not category:
                            # Find the best match among all normalized group names
                            best_match = None
                            best_score = 0.7  # Threshold for similarity (0.0 to 1.0)

                            for norm_name, orig_name in normalized_to_original.items():
                                # Skip very short names to avoid false matches
                                if len(norm_name) < 3 or len(normalized_group) < 3:
                                    continue

                                # Calculate similarity
                                similarity = string_similarity(normalized_group, norm_name)

                                # Check if this is a substring match
                                substring_match = norm_name in normalized_group or normalized_group in norm_name
                                if substring_match:
                                    similarity = max(similarity, 0.8)  # Boost similarity for substring matches

                                if similarity > best_score:
                                    best_match = orig_name
                                    best_score = similarity

                            if best_match:
                                category = group_to_category[best_match]
                                logger.info(f"Found fuzzy match for group '{group}' -> '{best_match}' (score: {best_score:.2f}) -> '{category}'")

                # 6. Default to 'Other' only if no match found
                if not category:
                    category = 'Other'
                    logger.info(f"No category match found for group '{group}', assigning to 'Other'")

                # Add time to the category total
                recalculated_time_by_category[category] += time

                # Add group to its category
                groups_by_category[category].append({'name': group, 'time': time})

            # Replace the original time_by_category with the recalculated one
            time_by_category = recalculated_time_by_category

            # Get categories and their times for charts
            categories = list(time_by_category.keys())

            # Convert minutes to hours with 1 decimal place - FORCE conversion
            category_times_minutes = list(time_by_category.values())
            category_times = []

            for time_in_minutes in category_times_minutes:
                # Ensure we're working with a number
                try:
                    time_in_minutes = float(time_in_minutes)
                    # Convert to hours with 1 decimal place
                    time_in_hours = round(time_in_minutes / 60.0, 1)
                    category_times.append(time_in_hours)
                    logger.debug(f"Converted category time {time_in_minutes} minutes to {time_in_hours} hours")
                except (ValueError, TypeError) as e:
                    logger.error(f"Error converting category time value: {time_in_minutes}, error: {e}")
                    # Default to 0 if conversion fails
                    category_times.append(0.0)

            # Log the category times for debugging
            logger.info(f"Category times (in hours): {list(zip(categories, category_times))}")

            # Log the results for debugging
            logger.info(f"Groups by category: {json.dumps(groups_by_category)[:500]}...")
            logger.info(f"Recalculated time by category: {json.dumps(time_by_category)}")
            logger.info(f"Categories: {categories}")
            logger.info(f"Category times: {category_times}")

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

            # Ensure all required categories are included
            required_categories = ['Training', 'Research', 'Coding', 'Work&Finance', 'Other']
            for cat in required_categories:
                if cat not in categories:
                    categories.append(cat)
                    logger.info(f"Added missing category: {cat}")
                    # Also add an empty entry to time_by_category
                    time_by_category[cat] = 0

            # Create category colors
            category_colors = {}
            for i, category in enumerate(categories):
                hue = i / max(1, len(categories))
                saturation = 0.8
                value = 0.9
                rgb = colorsys.hsv_to_rgb(hue, saturation, value)
                category_colors[category] = f"rgba({int(rgb[0] * 255)}, {int(rgb[1] * 255)}, {int(rgb[2] * 255)}, 0.7)"

            # 1. Create Category Distribution Chart (Pie Chart)
            visualizations["category_distribution"] = ChartData(
                chart_type="pie",
                title="Category Distribution",
                description="Time spent on each category",
                labels=categories,
                datasets=[{
                    "label": "Categories",
                    "data": category_times,
                    "backgroundColor": list(category_colors.values()),
                    "borderColor": [color.replace('0.7', '1') for color in category_colors.values()],
                    "borderWidth": 1
                }]
            )

            # 2. Create Category/Group Chart (Stacked Bar Chart)
            # Prepare data for stacked bar chart - one stack per category, with groups as segments
            stacked_datasets = []

            # Process each category to create stacks
            for category in categories:
                category_groups = groups_by_category.get(category, [])

                # Even if there are no groups, we still want to include the category in the chart
                # with a zero value to ensure all categories are displayed
                if not category_groups:
                    logger.info(f"No groups for category {category}, adding empty dataset")
                    # Add an empty dataset for this category
                    stacked_datasets.append({
                        "label": category,
                        "data": [0] * len(categories),  # Zero for all categories
                        "backgroundColor": category_colors.get(category, "rgba(200, 200, 200, 0.7)"),
                        "borderColor": category_colors.get(category, "rgba(200, 200, 200, 0.7)").replace('0.7', '1'),
                        "borderWidth": 1,
                        "stack": "stack1",
                        "categoryGroups": []
                    })
                    continue

                # Sort groups by time (descending)
                category_groups.sort(key=lambda x: x['time'], reverse=True)

                # Create data for this category's groups
                group_names = [group['name'] for group in category_groups]

                # Convert minutes to hours with 1 decimal place - FORCE conversion
                group_times_minutes = [group['time'] for group in category_groups]
                group_times = []

                # Log the original group times in minutes
                logger.info(f"Original group times for {category} (in minutes): {group_times_minutes}")

                for time_in_minutes in group_times_minutes:
                    # Ensure we're working with a number
                    try:
                        time_in_minutes = float(time_in_minutes)
                        # Convert to hours with 1 decimal place
                        time_in_hours = round(time_in_minutes / 60.0, 1)
                        group_times.append(time_in_hours)
                        logger.info(f"Converted group time {time_in_minutes} minutes to {time_in_hours} hours for {category}")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error converting time value: {time_in_minutes}, error: {e}")
                        # Default to 0 if conversion fails
                        group_times.append(0.0)

                # Generate colors for groups within this category
                group_colors = []
                base_color = category_colors[category]
                base_rgb = tuple(int(x) for x in base_color.replace('rgba(', '').replace(')', '').split(',')[:3])

                for i in range(len(category_groups)):
                    # Adjust brightness to create variation within the same hue
                    brightness = 0.5 + (0.5 * (i / max(1, len(category_groups))))
                    r = min(255, int(base_rgb[0] * brightness))
                    g = min(255, int(base_rgb[1] * brightness))
                    b = min(255, int(base_rgb[2] * brightness))
                    group_colors.append(f"rgba({r}, {g}, {b}, 0.7)")

                # Create dataset for this category's groups
                # Log the group times for debugging
                logger.info(f"Group times for {category}: {group_times}")

                stacked_datasets.append({
                    "label": category,
                    "data": group_times,  # This should already be converted to hours
                    "backgroundColor": group_colors,
                    "borderColor": [color.replace('0.7', '1') for color in group_colors],
                    "borderWidth": 1,
                    "stack": "stack1",  # All categories in the same stack
                    "categoryGroups": group_names  # Store group names for reference
                })

            # Get all group names across all categories
            all_groups = []
            for category in categories:
                for group in groups_by_category.get(category, []):
                    all_groups.append(group['name'])

            # Log the stacked datasets for debugging
            for dataset in stacked_datasets:
                logger.info(f"Stacked dataset for {dataset['label']}: {dataset['data']}")
                logger.info(f"Groups in this dataset: {dataset.get('categoryGroups', [])}")

            # Create a completely different approach for the stacked bar chart
            # Instead of using groups as labels, use categories as labels
            # Each dataset will represent a group within its category
            logger.error("*******************************************************************************")
            logger.error("* CREATING CUSTOM STACKED BAR CHART - THIS SHOULD APPEAR IN THE LOGS *")
            logger.error("*******************************************************************************")

            # First, create a new structure for the chart
            category_labels = categories  # Use categories as labels

            # Create a mapping of all groups to their categories
            # This will include all groups from time_by_group, not just those in groups_by_category
            all_groups_with_categories = {}

            # First, add all groups from groups_by_category
            for category in categories:
                for group in groups_by_category.get(category, []):
                    group_name = group['name']
                    all_groups_with_categories[group_name] = {
                        'category': category,
                        'time': group['time']
                    }
                    logger.info(f"Added group '{group_name}' to category '{category}' from groups_by_category")

            # Now, check if there are any groups in time_by_group that aren't in all_groups_with_categories
            # These would be groups that weren't properly assigned to a category
            for group_name, time in time_by_group.items():
                if group_name not in all_groups_with_categories:
                    # Try to find a category for this group using our fuzzy matching
                    normalized_group = normalize_group_name(group_name)

                    # Try to find a similar group that's already assigned to a category
                    best_match = None
                    best_score = 0.7  # Threshold for similarity
                    best_category = 'Other'

                    for known_group, info in all_groups_with_categories.items():
                        normalized_known = normalize_group_name(known_group)

                        # Skip very short names
                        if len(normalized_known) < 3 or len(normalized_group) < 3:
                            continue

                        # Calculate similarity
                        similarity = string_similarity(normalized_group, normalized_known)

                        # Check for substring match
                        if normalized_known in normalized_group or normalized_group in normalized_known:
                            similarity = max(similarity, 0.8)

                        if similarity > best_score:
                            best_match = known_group
                            best_score = similarity
                            best_category = info['category']

                    # If we found a good match, use its category
                    if best_match:
                        logger.info(f"Found similar group '{best_match}' (score: {best_score:.2f}) for unassigned group '{group_name}', assigning to category '{best_category}'")
                    else:
                        logger.info(f"No similar group found for '{group_name}', assigning to 'Other'")

                    # Add this group to our mapping
                    all_groups_with_categories[group_name] = {
                        'category': best_category,
                        'time': time
                    }

            # Now create datasets for each group
            group_datasets = []

            # Sort groups by time (descending) to make the chart more readable
            sorted_groups = sorted(all_groups_with_categories.items(),
                                   key=lambda x: x[1]['time'],
                                   reverse=True)

            # Create a dataset for each group
            for i, (group_name, info) in enumerate(sorted_groups):
                category = info['category']
                time_minutes = info['time']

                # Convert minutes to hours
                time_hours = round(time_minutes / 60.0, 1)

                # Create data array with zeros for all categories
                data = [0] * len(categories)

                # Find the index of this group's category
                try:
                    cat_idx = categories.index(category)
                    # Set the value only for this group's category
                    data[cat_idx] = time_hours

                    # Generate a color based on the category color
                    base_color = category_colors[category]
                    base_rgb = tuple(int(x) for x in base_color.replace('rgba(', '').replace(')', '').split(',')[:3])

                    # Adjust brightness to create variation within the same category
                    # Groups in the same category will have similar colors
                    brightness = 0.5 + (0.5 * (i / max(1, len(sorted_groups))))
                    r = min(255, int(base_rgb[0] * brightness))
                    g = min(255, int(base_rgb[1] * brightness))
                    b = min(255, int(base_rgb[2] * brightness))
                    color = f"rgba({r}, {g}, {b}, 0.7)"

                    # Create the dataset for this group
                    group_datasets.append({
                        "label": group_name,
                        "data": data,
                        "backgroundColor": color,
                        "borderColor": color.replace('0.7', '1'),
                        "borderWidth": 1,
                        "stack": "stack1"  # All groups in the same stack
                    })

                    logger.info(f"Created dataset for group '{group_name}' in category '{category}' with value {time_hours}h")
                except ValueError:
                    logger.error(f"Category '{category}' not found in categories list")

            # Create the stacked bar chart visualization with categories as labels
            visualizations["category_group_chart"] = ChartData(
                chart_type="bar",
                title="Categories with Groups Breakdown",
                description="Time spent on groups within each category (in hours)",
                labels=category_labels,  # Use categories as labels
                datasets=group_datasets,  # Each dataset is a group
                options={
                    "scales": {
                        "x": {
                            "stacked": True,
                            "title": {
                                "display": True,
                                "text": "Categories"
                            }
                        },
                        "y": {
                            "stacked": True,
                            "beginAtZero": True,
                            "title": {
                                "display": True,
                                "text": "Hours"
                            },
                            "ticks": {
                                "callback": "function(value) { return value.toFixed(1) + 'h'; }"
                            }
                        }
                    },
                    "plugins": {
                        "tooltip": {
                            "callbacks": {
                                "label": "function(context) { return context.dataset.label + ': ' + context.raw.toFixed(1) + 'h'; }"
                            }
                        }
                    }
                }
            )

            # Log the final chart data
            logger.info(f"Final category_group_chart data: {json.dumps(visualizations['category_group_chart'].dict(), indent=2)[:500]}...")

    logger.info(f"Created {len(visualizations)} visualizations for the report")

    # Format dates for display
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    # Convert minutes to hours with 1 decimal place for display
    hours = round(total_time / 60, 1)
    time_display = f"{hours:.1f} hours"

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
    logger.info(f"Generating charts for {len(visualizations)} visualizations: {list(visualizations.keys())}")
    for i, (chart_id, chart_data) in enumerate(visualizations.items()):
        logger.info(f"Processing visualization {i+1}/{len(visualizations)}: {chart_id}")
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
                # Data is already in hours, display with 1 decimal place
                time_display = f"{time_value:.1f}h"

                html += f"""
                                <tr>
                                    <td>{label}</td>
                                    <td>{time_display}</td>
                                </tr>
                """
        else:
            # For category distribution charts
            if chart_id == "category_distribution":
                # Use the time_by_category dictionary for accurate values
                for label in chart_data.labels:
                    # Get the actual time from time_by_category
                    time_value = time_by_category.get(label, 0)
                    # Convert to hours with 1 decimal place
                    hours_value = round(time_value / 60, 1)
                    time_display = f"{hours_value:.1f}h"

                    html += f"""
                                <tr>
                                    <td>{label}</td>
                                    <td>{time_display}</td>
                                </tr>
                    """
            elif chart_id == "category_group_chart":
                # Special handling for category_group_chart
                logger.info(f"Processing category_group_chart data table")

                # Use recalculated_time_by_category for accurate values
                for category, time_minutes in recalculated_time_by_category.items():
                    # Convert to hours with 1 decimal place
                    time_hours = round(time_minutes / 60.0, 1)
                    time_display = f"{time_hours:.1f}h"
                    logger.info(f"Category {category}: {time_minutes} minutes = {time_hours} hours")

                    # Generate the HTML for this row
                    html += f"""
                                <tr>
                                    <td>{category}</td>
                                    <td>{time_display}</td>
                                </tr>
                    """
            else:
                # For other charts
                for i, label in enumerate(chart_data.labels):
                    time_value = chart_data.datasets[0]["data"][i]
                    # For charts using hours, display with 1 decimal place
                    time_display = f"{time_value:.1f}h"
                    logger.info(f"Other chart {chart_id}, label {label}: {time_value}h")

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

        # End of chart container
        html += """
                    </div>
                </div>
            </div>
        """

        # Prepare chart script with more detailed configuration
        labels_json = json.dumps(chart_data.labels)
        datasets_json = json.dumps(chart_data.datasets)

        # Log the chart data for debugging
        logger.info(f"Chart {chart_id} data: {datasets_json[:200]}...")

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
                                "                // Display value directly as hours with 1 decimal place\n"
                                "                return `${context.dataset.label}: ${value.toFixed(1)}h`;\n"
                                "            }"
                    }
                }
            }
        }

        # If the chart data has options, merge them with the default options
        if hasattr(chart_data, 'options') and chart_data.options:
            logger.info(f"Merging custom options for chart {chart_id}")
            # Merge top-level options
            for key, value in chart_data.options.items():
                if key in chart_options and isinstance(chart_options[key], dict) and isinstance(value, dict):
                    # For nested dictionaries, merge them
                    chart_options[key].update(value)
                else:
                    # For simple values, replace them
                    chart_options[key] = value

        # Log chart configuration for debugging
        logger.info(f"Configuring chart {canvas_id} of type {chart_data.chart_type}")

        # Add specific options for bar charts
        if chart_data.chart_type == 'bar':
            # Check if this is the combined category-group chart
            is_stacked = any('stack' in dataset for dataset in chart_data.datasets)
            logger.info(f"Chart {chart_id} is_stacked: {is_stacked}")

            # Always treat category_group_chart as a stacked chart
            if is_stacked or chart_id == 'category_group_chart':
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
                            "text": "Hours"
                        },
                        "ticks": {
                            "callback": "function(value) { return (value).toFixed(1) + 'h'; }"
                        },
                        "beginAtZero": True,
                        "suggestedMax": 40
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

    # Format day strings for better display
    for day in sorted_days:
        try:
            day_date = date.fromisoformat(day)
            day_formatted = day_date.strftime("%A, %B %d, %Y")
        except ValueError:
            day_formatted = day

        day_data = daily_breakdown[day]
        # Convert to hours with 1 decimal place
        day_hours = round(day_data.total_time / 60, 1)
        day_time_display = f"{day_hours:.1f} hours"

        # Format the groups and categories for display
        groups_html = ""
        for group, time in day_data.time_by_group.items():
            # Convert to hours with 1 decimal place
            group_hours = round(time / 60, 1)
            groups_html += f"<li><strong>{group}:</strong> {group_hours:.1f}h</li>"

        categories_html = ""
        for category, time in day_data.time_by_category.items():
            # Convert to hours with 1 decimal place
            category_hours = round(time / 60, 1)
            categories_html += f"<li><strong>{category}:</strong> {category_hours:.1f}h</li>"

        html += f"""
            <div class="daily-item">
                <h3>{day_formatted}</h3>
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
