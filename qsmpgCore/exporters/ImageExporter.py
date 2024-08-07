import os

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import matplotlib.style as mplstyle
mplstyle.use('fast')
plt.switch_backend('agg')
# plt.switch_backend('Cairo')
from ..structures import Dataset, Place

def fix_filename(sourcestring,  removestring="#%&}{$!\'\"@+`|:/,=.\\[]<>*?\n\t"):
    """
    Replaces special characters in a string with underscores.

    Args:
        sourcestring (str): The string to be processed.
        removestring (str): A string containing the special characters to be removed.

    Returns:
        str: The modified string with special characters replaced with underscores.
    """
    return ''.join([c if c not in removestring else '_' for c in sourcestring])

def expand_value(value: float, length: int):
    """
    Creates a list of repeated values.

    Args:
        value (float): The value to be repeated.
        length (int): The number of times the value should be repeated.

    Returns:
        list: A list containing the repeated value.
    """
    return [value] * length

def export_to_image_files(destination_path, structured_dataset: Dataset, subFolderName='Static_Image_Reports'):
    """Exports data to image files in a specified destination folder.

    Args:
        destination_path (str): The path to the destination folder.
        structured_dataset (Dataset): A dataset object containing the data to be exported.
        subFolderName (str, optional): The name of the subfolder within the destination folder. Defaults to 'Static_Image_Reports'.
    """
    # Create the destination folder if it doesn't exist
    image_subfolder_path = os.path.join(destination_path, subFolderName)
    os.makedirs(image_subfolder_path, exist_ok=True)
    context = FigureContext(structured_dataset)

    # update and save plt figures
    for place in structured_dataset.places.values():
        context.update_subplots(place)
        context.plt_figure.savefig(os.path.join(image_subfolder_path, f'{fix_filename(place.id)}.png'), dpi=130)
    plt.close('all')

class FigureContext:
    """
    A context manager for generating plots based on a given Dataset.
    This class provides a standardized way to configure and create multiple 
    axes for plotting various types of data, including accumulations, current 
    seasons, forecasts, and more. It is designed to be used within the scope 
    of an ImageExporter instance.

    Attributes:
        plot_colors (dict): A dictionary mapping dataset types to specific 
            colors used in the plots.
        plot_types (dict): A dictionary mapping dataset types to the type of 
            plot to use (e.g., 'bar', 'line', 'area').
        custom_x (dict): A dictionary mapping dataset types to customized 
            x-axis values for each plot.
        thick_lines (list): A list of line styles that should be displayed 
            with a thicker line width.
        dashed_lines (list): A list of line styles that should be displayed 
            with a dashed line style.
    """
    def __init__(self, dataset: Dataset):
        self.plot_colors = {
            'Current Season': '#0000FF',
            'Current Season Accumulation': '#0000FF',
            'Current Season Total': '#0000FF',
            'Seasonal Accumulations': '#78ADD2',
            'Forecast': '#FF00FF',
            'Forecast Accumulation': '#FF00FF',
            'LTA': '#FF0000',
            'Median': '#000000',
            'LTA±20%': '#00AFE5',
            'Climatology Average': '#FF0000',
            'LTA±St. Dev.': '#008000',
            '(33, 67) Pctl.': '#000000',
            'Ensemble Med.': '#000000',
            'E. LTA±St. Dev.': '#FFA500',
            'E. (33, 67) Pctl.': '#0000FF',
            '67 Pctl.': '#00FF00',
            'D0: 31 Pctl.': '#FFFF00',
            'D1: 21 Pctl.': '#FCD37F',
            'D2: 11 Pctl.': '#FFAA00',
            'D3: 6 Pctl.': '#E60000',
            'D4: 3 Pctl.': '#730000',
        }

        self.plot_types = {
            'Current Season': 'bar',
            'Current Season Total': 'bar',
            'Seasonal Accumulations': 'bar',
            'Forecast': 'bar',
            'LTA±20%': 'area-line-range',
            'LTA±St. Dev.': 'scatter',
            '(33, 67) Pctl.': 'scatter',
            'E. LTA±St. Dev.': 'scatter',
            'E. (33, 67) Pctl.': 'scatter',
            # 'D4: 3 Pctl.': 'area',
            # 'D3: 6 Pctl.': 'area',
            # 'D2: 11 Pctl.': 'area',
            # 'D1: 21 Pctl.': 'area',
            # 'D0: 31 Pctl.': 'area',
        }

        x_period_labels = dataset.properties.sub_season_monitoring_ids
        monitoring_length = len(x_period_labels)
        current_length = dataset.properties.current_season_length-dataset.parameters.is_forecast
        current_mon_length = dataset.properties.current_season_length-dataset.properties.sub_season_offset-dataset.parameters.is_forecast
        season_quantity = len(dataset.properties.year_ids)
        self.custom_x = {
            'Current Season': range(current_length),
            'Current Season Accumulation': range(current_mon_length),
            'Current Season Total': [season_quantity],
            'Seasonal Accumulations': range(season_quantity),
            'Forecast Accumulation': [current_mon_length-1, current_mon_length],
            'Forecast': [current_length],
            'LTA±St. Dev.': [monitoring_length-1]*2,
            '(33, 67) Pctl.': [monitoring_length-1]*2,
            'E. LTA±St. Dev.': [monitoring_length-1]*2,
            'E. (33, 67) Pctl.': [monitoring_length-1]*2,
        }

        self.thick_lines = ['Climatology Average', 'LTA', 'Median', 'Ensemble Med.', 
                            'Current Season Accumulation', 'Forecast Accumulation']
        self.dashed_lines = ['Ensemble Med.']

        self.plt_figure = plt.figure(
            num=0,
            layout='tight',
            figsize=(16, 9),
            clear=True
        )
        # grid with two rows and three columns
        self.plot_grid = plt.GridSpec(2, 3, figure=self.plt_figure)

        self.axis1_accumulations = self.plt_figure.add_subplot(self.plot_grid[0, 0])
        self.axis2_current = self.plt_figure.add_subplot(self.plot_grid[0, 1:3])
        self.axis3_ensemble = self.plt_figure.add_subplot(self.plot_grid[1, 0])
        self.axis4_accumulations_current = self.plt_figure.add_subplot(self.plot_grid[1, 1:3])

    def update_subplots(self, place: Place):
        """
        Updates the subplots based on the given Place.

        This method calls the `update_plot` method for each axis in turn,
        passing the corresponding data to plot.
        
        Parameters:
            place (Place): The Place instance containing the data and metadata.
        """
        self.update_plot(self.axis1_accumulations, make_accumulations_data(place))
        self.update_plot(self.axis2_current, make_current_data(place))
        self.update_plot(self.axis3_ensemble, make_ensemble_data(place))
        self.update_plot(self.axis4_accumulations_current, make_accumulations_current_data(place))

    def update_plot(self, axis: Axes, data: tuple):
        """Updates the plot for a given axis.

        This method is called by `update_subplots` to create or update the 
        plots in each axis. It uses the provided data and metadata to configure 
        the plot.

        Parameters:
            axis (Axes): The axis to update.
            data (tuple): A tuple containing the plot data, table data array,
                and metadata for the plot.
        """
        axis.clear()
        plot_data, table_data_array, metadata = data
        is_many_seasons = len(metadata['selected years']) > 10
        
        font_size = 8

        x_ticks = metadata['x ticks']
        x_length = len(x_ticks)
        x_coords = range(x_length)

        axis.set_title(metadata['title'])
        axis.set_xlabel(metadata['x label'])
        axis.set_ylabel(metadata['y label'])
        axis.grid()
        axis.set_xticks(x_coords, x_ticks, rotation=35, fontsize=font_size)
        axis.set_xlim([-.5, x_length-.5])
        for id, plot_data in plot_data.items():
            is_season_and_many_seasons = is_many_seasons and (id in metadata['selected years'])

            x = self.custom_x[id] if id in self.custom_x else range(x_length)
            y = plot_data
            color = 'darkgray' if is_season_and_many_seasons else self.plot_colors[id] if id in self.plot_colors else None
            line_width = 3 if id in self.thick_lines else 1
            line_style = 'dashed' if id in self.dashed_lines else'solid'
            data_label = id if not is_season_and_many_seasons else None
            if id in self.plot_types:
                if self.plot_types[id] =='bar':
                    axis.bar(x, y, color=color, lw=line_width, label=data_label)
                elif self.plot_types[id] == 'area':
                    axis.fill_between(x, y, color=color+'22', edgecolor=color+'BB', lw=line_width, label=data_label)
                elif self.plot_types[id] == 'area-line-range':
                    axis.fill_between(x, y[0], y[1], color=color, lw=line_width, label=data_label, alpha=.3)
                elif self.plot_types[id] == 'scatter':
                    axis.scatter(x, [y[0],y[1]], color=color, lw=line_width, label=data_label, s=20, zorder=99)
            else: # line plot (default)
                axis.plot(x, y, color=color, lw=line_width, ls=line_style, label=data_label)
        if 'ylim fix value' in metadata:
            axis.set_ylim(bottom=metadata['ylim fix value'])

        if table_data_array is not None:
            cell_alpha = .6
            cell_height = 0.05
            anchor_xy = [0.010, 0.940]
            for i, table_data in enumerate(table_data_array):
                table_height = cell_height*(len(table_data)-1)
                bbox = [anchor_xy[0], anchor_xy[1]-table_height, metadata['table width'], table_height]
                table = axis.table(cellText=table_data[1:], bbox=bbox, 
                                    zorder=100, cellLoc='center', fontsize=font_size)
                table.auto_set_font_size(False)
                for col_num in range(len(table_data[1])):
                    table.auto_set_column_width(col_num)
                for key,cell in table.get_celld().items():
                    if key[0]==0 or key[1]==0: cell.set_color('lightgray')
                    else: cell.set_color('white')
                    cell.set_edgecolor('black')
                    cell.set_alpha(cell_alpha)
                    cell.PAD = 0
                table.set_fontsize(font_size)
                    
                title_bbox = [bbox[0], bbox[1]+table_height, bbox[2], cell_height]
                title_table = axis.table(cellText=[table_data[0]], bbox=title_bbox,
                                        zorder=100, cellLoc='center', fontsize=font_size)
                title_table.auto_set_font_size(False)
                title_table.set_fontsize(font_size)
                title_cell = title_table.get_celld()[(0,0)]
                title_cell.set_color('lightskyblue')
                title_cell.set_edgecolor('black')
                title_cell.set_alpha(cell_alpha)
                title_cell.PAD = 0

                anchor_xy = [bbox[0], bbox[1]-cell_height-0.025]
            
        axis.legend(
            loc='upper center',
            bbox_to_anchor=(0.5, -0.30),
            ncol=4,
            fontsize=8,
            fancybox=False,
            borderaxespad=0,
            handletextpad=0.4,
            columnspacing=1,
        )

def make_accumulations_data(place: Place):
    """
    Creates a tuple containing the plot data, table data array, and metadata 
    for the seasonal rainfall accumulation.

    Parameters:
        place (Place): The Place instance containing the relevant data and 
            metadata.

    Returns:
        A tuple of three elements:
            1. Dictionary with statistical for the given place.
            2. A list of table data for the axis tables.
            3. Dictionary with metadata for the plot.
    """
    props = place.parent.properties
    selected_season_stats = place.selected_years_seasonal_stats
    selected_place_stats = place.selected_years_place_stats
    place_stats = place.place_stats
    current_index = len(selected_place_stats['Current Season Accumulation'])-1
    data = {
        **selected_season_stats['Sum'],
        'Median': place_stats['Median'],
        'LTA±20%': [place_stats['LTA']*1.20, place_stats['LTA']*0.80],
        'LTA±St. Dev.': [place_stats['LTA'][-1]+place_stats['St. Dev.'][-1], 
                        place_stats['LTA'][-1]-place_stats['St. Dev.'][-1]],
        'LTA': place_stats['LTA'],
        'Current Season Accumulation': place_stats['Current Season Accumulation'],
        '(33, 67) Pctl.': [place_stats['Pctls.'][0], 
                           place_stats['Pctls.'][1]],
    }
    if place_stats['forecast'][0] is not None:
        data['Forecast Accumulation'] = [
            place_stats['Current Season Accumulation'][-1], 
            place_stats['Current Season Accumulation'][-1]+place_stats['forecast'][0]]
    table_data_array = [
        [['Total Current Dekad'],
        [round(selected_place_stats['Current Season Accumulation'][-1])],
        ],
        [['Assessment at current dekad'],
        ['', 'Sel. Yrs.', 'Clim.'],
        ['LTA C. Dk.', round(selected_place_stats['LTA'][current_index]), round(place.place_stats['LTA'][current_index])],
        ['C. Dk./LTA Pct.', round(selected_place_stats['C. Dk./LTA'][current_index]*100), round(place.place_stats['C. Dk./LTA'][current_index]*100)]],
    ]
    metadata = {
        'title': 'Seasonal Accumulations',
        'selected years': place.selected_years,
        'x ticks': props.sub_season_monitoring_ids,
        'x label': f'Time ({props.period_unit_id}s)',
        'y label': 'Rainfall (mm)',
        'table width': 0.45,
    }
    return data, table_data_array, metadata

def make_current_data(place: Place):
    """
    Creates a tuple containing the plot data, table data array, and metadata
    for the current rainfall status.
    
    Parameters:
        place (Place): The Place instance containing the relevant data and
            metadata.
        
    Returns:
        A tuple of three elements:
            1. Dictionary with current season and climatology average data,
                as well as forecast data if available.
            2. A list of table data for the axis tables.
            3. Dictionary with metadata for the plot.
    """
    props = place.parent.properties
    selected_place_stats = place.selected_years_place_stats
    data = {
        'Current Season': selected_place_stats['Current Season'],
        'Climatology Average': selected_place_stats['Avg.'],
    }
    if selected_place_stats['forecast'][0] is not None:
        data['Forecast'] = selected_place_stats['forecast']
    table_data_array = [
        [['Seasonal Analysis'],
        ['', 'Sel. Yrs.', 'Clim.'],
        ['LTA', round(selected_place_stats['LTA'][-1]), round(place.place_stats['LTA'][-1])],
        ['St. Dev.', round(selected_place_stats['St. Dev.'][-1]), round(place.place_stats['St. Dev.'][-1])]],
    ]

    clim_start = props.climatology_year_ids[0]
    clim_end = props.climatology_year_ids[-1]
    metadata = {
        'title': f'Current Rainfall Status ({props.current_season_id}). Climatology: [{clim_start}, {clim_end}]',
        'selected years': place.selected_years,
        'x ticks': props.sub_season_ids,
        'x label': f'Time ({props.period_unit_id}s)',
        'y label': 'Rainfall (mm)',
        'table width': 0.2,
    }
    return data, table_data_array, metadata

def make_ensemble_data(place: Place):
    """
    Creates a tuple containing the plot data, table data array, and metadata
    for the ensemble.
    
    Parameters:
        place (Place): The Place instance containing the relevant data and
            metadata.
        
    Returns:
        A tuple of three elements:
            1. Dictionary with ensemble accumulations and statistics.
            2. A list of table data for the axis tables.
            3. Dictionary with metadata for the plot.
    """
    props = place.parent.properties
    selected_season_stats = place.selected_years_seasonal_stats
    selected_place_stats = place.selected_years_place_stats
    place_stats = place.place_stats
    data = {
        **selected_season_stats['Ensemble Sum'],
        'LTA±20%': [place_stats['LTA']*1.20, place_stats['LTA']*0.80],
        'LTA±St. Dev.': [place_stats['LTA'][-1]+place_stats['St. Dev.'][-1], 
                        place_stats['LTA'][-1]-place_stats['St. Dev.'][-1]],
        'LTA': place_stats['LTA'],
        '(33, 67) Pctl.': [place_stats['Pctls.'][0], 
                           place_stats['Pctls.'][1]],
        'Ensemble Med.': selected_place_stats['Ensemble Med.'],
        'E. (33, 67) Pctl.': [selected_place_stats['E. Pctls.'][0], 
                              selected_place_stats['E. Pctls.'][1]],
        'E. LTA±St. Dev.': [selected_place_stats['E. LTA'][-1]+selected_place_stats['St. Dev.'][-1], 
                        selected_place_stats['E. LTA'][-1]-selected_place_stats['St. Dev.'][-1]],
        'Current Season Accumulation': place_stats['Current Season Accumulation'],
    }
    table_data_array = [
        [['Proj. at EoS'],
        ['', 'Sel. Yrs.', 'Clim.'],
        ['Ensemble Med.', round(selected_place_stats['Ensemble Med.'][-1]), round(place.place_stats['Ensemble Med.'][-1])],
        ['LTA', round(selected_place_stats['LTA'][-1]), round(place.place_stats['LTA'][-1])],
        ['Ensemble Med./LTA Pct.', round(selected_place_stats['Ensemble Med./LTA'][-1]*100), round(place.place_stats['Ensemble Med./LTA'][-1]*100)]],
        [['Prob. at EoS'],
        ['', 'Sel. Yrs.', 'Clim.'],
        ['Ab. Normal', round(selected_place_stats['E. Probabilities'][2]*100), round(place.place_stats['E. Probabilities'][2]*100)],
        ['Normal', round(selected_place_stats['E. Probabilities'][1]*100), round(place.place_stats['E. Probabilities'][1]*100)],
        ['Be. Normal', round(selected_place_stats['E. Probabilities'][0]*100), round(place.place_stats['E. Probabilities'][0]*100)]],
    ]
    metadata = {
        'title': 'Ensemble',
        'selected years': place.selected_years,
        'x ticks': props.sub_season_monitoring_ids,
        'x label': f'Time ({props.period_unit_id}s)',
        'y label': 'Rainfall (mm)',
        'table width': 0.56,
    }
    return data, table_data_array, metadata

def make_accumulations_current_data(place: Place):
    """
    Creates a tuple containing the plot data, table data array, and metadata
    for seasonal rainfall accumulations up to current period.
    
    Parameters:
        place (Place): The Place instance containing the relevant data and
            metadata.
        
    Returns:
        A tuple of three elements:
            1. Dictionary with seasonal accumulations and statistics.
            2. A list of table data for the axis tables.
            3. Dictionary with metadata for the plot.
    """
    props = place.parent.properties
    season_stats = place.seasonal_stats
    place_stats = place.place_stats
    selected_place_stats = place.selected_years_place_stats
    current_index = len(selected_place_stats['Current Season Accumulation'])-1
    x_ticks = props.year_ids + [props.current_season_id]
    x_length = len(x_ticks)
    data = {
        'Seasonal Accumulations': [s[current_index] for s in season_stats['Sum'].values()],
        'Current Season Total': [selected_place_stats['Current Season Accumulation'][-1]],
        'Climatology Average': [place_stats['LTA'][current_index]] * x_length,
        '67 Pctl.': [place_stats['Drought Severity Pctls.'][5]] * x_length,
        '33 Pctl.': [place_stats['Drought Severity Pctls.'][4]] * x_length,
        'D1: 21 Pctl.': [place_stats['Drought Severity Pctls.'][3]] * x_length,
        'D2: 11 Pctl.': [place_stats['Drought Severity Pctls.'][2]] * x_length,
        'D3: 6 Pctl.': [place_stats['Drought Severity Pctls.'][1]] * x_length,
        'D4: 3 Pctl.': [place_stats['Drought Severity Pctls.'][0]] * x_length,
    }
    table_data_array = [
        [['Historical Rainfall Statistics'],
        ['', 'Value'],
        ['Clim. Avg. C. Dk.', round(place_stats['LTA'][current_index])],
        # ['Sel. Yrs. Avg. C. Dk.', round(selected_place_stats['LTA'][current_index])],
        ['67 Pctl.', round(place_stats['Drought Severity Pctls.'][5])],
        ['33 Pctl.', round(place_stats['Drought Severity Pctls.'][4])],
        # ['D1: 21 Pctl.', round(place_stats['Drought Severity Pctls.'][3])],
        ['11 Pctl.', round(place_stats['Drought Severity Pctls.'][2])],
        # ['D3: 6 Pctl.', round(place_stats['Drought Severity Pctls.'][1])],
        # ['D4: 3 Pctl.', round(place_stats['Drought Severity Pctls.'][0])]
        ],
    ]

    metadata = {
        'title': f'Seasonal Rainfall Accumulation up to Current Dekad for {place.id}',
        'selected years': place.selected_years,
        'x ticks': x_ticks,
        'x label': f'Time (Years)',
        'y label': 'Rainfall (mm)',
        'table width': 0.2,
        'ylim fix value': min(min(data['Seasonal Accumulations']), min(data['Current Season Total']))*.9,
    }
    return data, table_data_array, metadata
