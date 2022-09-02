DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `token` varchar(255) NOT NULL,
  `leader_card_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);
DROP TABLE IF EXISTS `rooms`;
CREATE TABLE `rooms` (
  `room_id` bigint not null auto_increment,
  `status` int not null,
  `live_id` int not null,
  `j_usr_cnt` int not null,
  `m_usr_cnt` int not null,
  `hst_id` int not null,
  `users` text,
  PRIMARY KEY (`room_id`)
);