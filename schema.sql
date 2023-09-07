use webapp;

DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `token` varchar(255) NOT NULL,
  `leader_card_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);


DROP TABLE IF EXISTS `room_member`;
DROP TABLE IF EXISTS `room`;

CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `owner_id` bigint NOT NULL,
  `live_id` bigint NOT NULL,
  PRIMARY KEY (`room_id`)
);

CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `difficulty` int NOT NULL,
  PRIMARY KEY (`room_id`, `user_id`),
  FOREIGN KEY (`room_id`) REFERENCES `room` (`room_id`)
);
