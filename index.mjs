require('dotenv').config();
const Mustache = require('mustache');
import fetch from 'node-fetch';
import fs from 'fs';

const MUSTACHE_MAIN_DIR = './main.mustache';

let DATA = {
  refresh_date: new Date().toLocaleDateString('en-GB', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    timeZoneName: 'short',
    timeZone: 'Asia/Chennai',
  }),
};

async function setWeatherInformation() {
  const response = await fetch(
    `https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/Chennai?unitGroup=metric&key=${process.env.VISUAL_CROSSING_API_KEY}&contentType=json`
  );
  
  const weatherData = await response.json();

  DATA.city_temperature = Math.round(weatherData.main.temp);
  DATA.feels_like_temp = Math.round(weatherData.main.feels_like);
  DATA.city_weather = weatherData.weather[0].description;
  DATA.weather_icon = 'http://visualcrossing.org/img/w/' + weatherData.weather[0].icon + '.png';
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
}

// async function setInstagramPosts() {
//   const instagramImages = await puppeteerService.getLatestInstagramPostsFromAccount('pinusonline', 3);
//   DATA.img1 = instagramImages[0];
//   DATA.img2 = instagramImages[1];
//   DATA.img3 = instagramImages[2];
// }

async function generateReadMe() {
  const data = await fs.promises.readFile(MUSTACHE_MAIN_DIR, 'utf8');
  const output = Mustache.render(data, DATA);
  await fs.promises.writeFile('README.md', output);
}

async function action() {
  /**
   * Fetch weather
   */
  await setWeatherInformation();

  /**
   * Get pictures
   */
  // await setInstagramPosts();

  /**
   * Generate README
   */
  await generateReadMe();
}

action();
