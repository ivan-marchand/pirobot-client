import logging
import pygame

logger = logging.getLogger(__name__)


class GamePad():
    running = False

    @staticmethod
    def start_loop(device_name=None, callback=dict()):
        joysticks = {}

        GamePad.running = True
        while GamePad.running:
            try:
                if not pygame.get_init():
                    pygame.init()
                for event in pygame.event.get():
                    # Buttons
                    if event.type in [pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP]:
                        joystick = joysticks[event.instance_id]
                        callback["button"](joystick, event.button, event.type == pygame.JOYBUTTONDOWN)
                    # AXIS
                    if event.type == pygame.JOYAXISMOTION:
                        joystick = joysticks[event.instance_id]
                        callback["axis_motion"](joystick, event.axis)
                    # HAT
                    if event.type == pygame.JOYHATMOTION:
                        joystick = joysticks[event.instance_id]
                        callback["hat_motion"](joystick, event.hat, event.value[0], event.value[1])

                    # Joystick Added
                    if event.type == pygame.JOYDEVICEADDED:
                        joy = pygame.joystick.Joystick(event.device_index)
                        joysticks[joy.get_instance_id()] = joy
                        print(f"Joystick {joy.get_name()} ({joy.get_guid()}) connected")

                    # Joystick Remove
                    if event.type == pygame.JOYDEVICEREMOVED:
                        del joysticks[event.instance_id]
                        print(f"Joystick {joy.get_name()} ({joy.get_guid()}) disconnected")

            except KeyboardInterrupt:
                raise
            except:
                logger.error("Unable to process gamepad event", exc_info=True)
                continue

    @staticmethod
    def stop_loop():
        GamePad.running = False
