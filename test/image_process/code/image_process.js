'use strict';
var jimp = require("jimp");
var fs = require("fs")
module.exports.resize = function(event, context, callback) {
  // 传入的event是png格式的图片，将其写入到tmp目录下。
  fs.writeFileSync("/tmp/serverless.png", event)

  // 读取/tmp目录下的png图片，调用jimp库完成resize，将结果图片写入到/tmp目录。
  jimp.read("/tmp/serverless.png", function(err, image) {
    if (err) {
      console.error("failed to read image");
      callback(err)
      return
    }
    image.resize(128, 128)
    .write("/tmp/serverless_128.png", function(err) {
      if (err) {
        console.error("failed to write image");
        callback(err)
        return
      }

      // 从/tmp目录读取结果图片，并作为response返回。
      callback(null, fs.readFileSync("/tmp/serverless_128.png"))
    })
  });
};
