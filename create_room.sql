DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int NOT NULL,
  `owner` bigint NOT NULL,
  `status` int NOT NULL,
  PRIMARY KEY (`room_id`),
  UNIQUE KEY `owner` (`owner`)
);