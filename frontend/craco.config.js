// craco.config.js
module.exports = {
    webpack: {
      alias: {
        "#minpath": require.resolve("path-browserify")
      }
    }
  };