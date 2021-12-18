# F1_Telemetry_Charts
Small python project that creates charts to compare the performance of 2 cars during an F1 session

The data is provided by the [FastF1 API](https://github.com/theOehrly/Fast-F1) and formated using matplotlib.

## Usage
### Notebooks
#### Variables
To generate the graphs you need to modify the variables at the top of the notebook
* **RaceNumber** is the round number of the race you want to analyze
* **Title** will be displayed in bold on top of all the graphs
* **Driver_name** is the driver abreviated name used on the timing screens (Exemples : Hamilton -> HAM, Verstappen -> VER)
* **Color** you can use team colors with the [fastF1 API following this syntax](https://theoehrly.github.io/Fast-F1/plotting.html#fastf1.plotting.TEAM_COLORS) : plotting.TEAM_COLORS['nameOfTheTeam']

### Output Directory
You'll have to create the directory where the charts will be generated and give the path in the directory variable.

## Example
Examples are provided in the Telemtry directory

![example](https://raw.githubusercontent.com/Nelson-Jnrnd/F1_Telemetry_Charts/main/Telemetry/2021/TUR/Alpine/Qualifying/telemetrySpeed.png)
