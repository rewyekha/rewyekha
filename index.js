require('dotenv').config();
const Mustache = require('mustache');
const fetch = require('node-fetch');
const fs = require('fs');
// const puppeteerService = require('./services/puppeteer.service');

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
  await fetch(
    `https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/Chennai?unitGroup=metric&key=UE9M9BKJQVKZKBUXBFCBM2H2E&contentType=json`
  )
    .then(r => r.json())
    .then(r => {
      DATA.city_temperature = Math.round(r.main.temp);
      DATA.feels_like_temp = Math.round(r.main.feels_like);
      DATA.city_weather = r.weather[0].description;
      /** DATA.weather_icon = 'http://openweathermap.org/img/w/' + r.weather[0].icon + '.png'; */
      DATA.humidity = r.main.humidity;
      DATA.sun_rise = new Date(r.sys.sunrise * 1000).toLocaleString('en-GB', {
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'Asia/Chennai',
      });
      DATA.sun_set = new Date(r.sys.sunset * 1000).toLocaleString('en-GB', {
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'Asia/Chennai',
      });
    });
}

/** 
async function setInstagramPosts() {
  const instagramImages = await puppeteerService.getLatestInstagramPostsFromAccount('pinusonline', 3);
  DATA.img1 = instagramImages[0];
  DATA.img2 = instagramImages[1];
  DATA.img3 = instagramImages[2];
}

async function generateReadMe() {
  await fs.readFile(MUSTACHE_MAIN_DIR, (err, data) => {
    if (err) throw err;
    const output = Mustache.render(data.toString(), DATA);
    fs.writeFileSync('README.md', output);
  });
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

  /**
   * Bye bye service 👋
   */
  // await puppeteerService.close();


action();