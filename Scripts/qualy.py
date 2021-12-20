import os
import pandas as pd
import fastf1 as ff1
from matplotlib import pyplot as plt
from fastf1 import plotting

plotting.setup_mpl()
ff1.Cache.enable_cache('../cache')


def load_session(year, race_number):
    quali = ff1.get_session(year, race_number, 'Q')
    laps = quali.load_laps(with_telemetry=True)
    return laps


def generate_chart(driver1_name, driver1_fullname, driver1_color, driver1_lap,
                   driver2_name, driver2_fullname, driver2_color, driver2_lap,
                   graphline_width, title, directory):
    driver1_data = driver1_lap.telemetry
    driver2_data = driver2_lap.telemetry

    fig, ax = plt.subplots()

    ax.plot(driver1_data['Distance'], driver1_data['Speed'], color=driver1_color, linewidth=graphline_width, label=driver1_name)
    ax.plot(driver2_data['Distance'], driver2_data['Speed'], color=driver2_color, linewidth=graphline_width, label=driver2_name)

    ax.set_title(title)
    ax.set_xlabel("Distance (m)")
    ax.set_ylabel("Speed (kph)")
    ax.legend(bbox_to_anchor=(0, 1), loc=3)
    plt.savefig(directory + 'telemetrySpeed.png', dpi=1200)
    plt.show()


def main():
    teams = pd.read_csv('input/team.csv')
    laps = load_session(2021, 22)
    for i, team in teams.iterrows():
        driver1_lap = laps.pick_driver(team['driver1_name']).pick_fastest()
        driver2_lap = laps.pick_driver(team['driver2_name']).pick_fastest()

        directory = '../Telemetry/2021/AE/' + team['name'] + '/qualifying/'
        dir_exist = os.path.exists(directory)
        if not dir_exist:
            os.makedirs(directory)

        generate_chart(
            team['driver1_name'], team['driver1_fullname'], plotting.TEAM_COLORS[team['name']],
            driver1_lap,
            team['driver2_name'], team['driver2_fullname'], team['alternate_color'], driver2_lap,
            0.3, 'Abu Dhabi Qualy', directory)


if __name__ == "__main__":
    main()
