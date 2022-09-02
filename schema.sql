DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NOT NULL,
  `token` varchar(255) DEFAULT NOT NULL,
  `leader_card_id` int DEFAULT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int DEFAULT NOT NULL,
  `joined_user_count` int DEFAULT NOT NULL,
  `max_user_count` int DEFAULT NOT NULL,
  `wait_room_status` int DEFAULT NOT NULL,
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` bigint NOT
)