import dotenv from 'dotenv';
import Mustache from 'mustache';
import fetch from 'node-fetch';
import fs from 'fs';

dotenv.config();

const MUSTACHE_MAIN_DIR = './main.mustache';

const tzOffsetMs = 330 * 60 * 1000; // Offset for Asia/Kolkata, which Chennai follows (330 minutes = 5 hours and 30 minutes)
let refresh_date = new Date(Date.now() + tzOffsetMs).toLocaleDateString('en-GB', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric'
});


async function setWeatherInformation() {
  try {
    const response = await fetch(
      `https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/Chennai?unitGroup=metric&key=${process.env.VISUAL_CROSSING_API_KEY}&contentType=json`
    );
    
    const weatherData = await response.json();

    DATA.city_temperature = Math.round(weatherData.main.temp);
    DATA.feels_like_temp = Math.round(weatherData.main.feels_like);
    DATA.city_weather = weatherData.weather[0].description;
    DATA.weather_icon = `http://visualcrossing.org/img/w/${weatherData.weather[0].icon}.png`;
    DATA.humidity = weatherData.main.humidity;
    DATA.sun_rise = new Date(weatherData.sys.sunrise * 1000).toLocaleString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Asia/Chennai',
    });
    DATA.sun_set = new Date(weatherData.sys.sunset * 1000).toLocaleString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Asia/Chennai',
    });
  } catch (error) {
    console.error('Error fetching weather data:', error);
  }
}

async function generateReadMe() {
  try {
    const data = await fs.promises.readFile(MUSTACHE_MAIN_DIR, 'utf8');
    const output = Mustache.render(data, DATA);
    await fs.promises.writeFile('README.md', output);
  } catch (error) {
    console.error('Error generating README:', error);
  }
}

async function action() {
  /**
   * Fetch weather
   */
  await setWeatherInformation();

  /**
   * Generate README
   */
  await generateReadMe();
}

action();
