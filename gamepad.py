import logging
import pygame
import threading

logger = logging.getLogger(__name__)


class GamePad():
    running = False
    thread = None

    @staticmethod
    def start_loop(callback):
        joysticks = {}
        clock = pygame.time.Clock()

        GamePad.running = True
        while GamePad.running:
            try:
                if not pygame.get_init():
                    pygame.init()
                for event in pygame.event.get():
                    # Buttons
                    if event.type in [pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP]:
                        joystick = joysticks[event.instance_id]
                        if "button" in callback:
                            callback["button"](joystick, event.button, event.type == pygame.JOYBUTTONDOWN)
                    # AXIS
                    if event.type == pygame.JOYAXISMOTION:
                        joystick = joysticks[event.instance_id]
                        if "axis_motion" in callback:
                            callback["axis_motion"](joystick, event.axis)
                    # HAT
                    if event.type == pygame.JOYHATMOTION:
                        joystick = joysticks[event.instance_id]
                        if "hat_motion" in callback:
                            callback["hat_motion"](joystick, event.hat, event.value[0], event.value[1])

                    # Joystick Added
                    if event.type == pygame.JOYDEVICEADDED:
                        joy = pygame.joystick.Joystick(event.device_index)
                        joysticks[joy.get_instance_id()] = joy
                        print(f"Joystick {joy.get_name()} ({joy.get_guid()}) connected")
                        if "joystick_added" in callback:
                            callback["joystick_added"](joy)

                    # Joystick Remove
                    if event.type == pygame.JOYDEVICEREMOVED:
                        print(f"Joystick {joy.get_name()} ({joy.get_guid()}) disconnected")
                        if "joystick_removed" in callback:
                            callback["joystick_removed"](joysticks[event.instance_id])
                        del joysticks[event.instance_id]

            except KeyboardInterrupt:
                raise
            except:
                logger.error("Unable to process gamepad event", exc_info=True)
                continue
            finally:
                # Limit CPU used by the loop
                fps = 30
                clock.tick(fps)
        pygame.quit()
        print("Stopping gamepad loop")

    @staticmethod
    def start_gamepad(callback):
        if GamePad.thread is not None:
            GamePad.stop_gamepad()
        GamePad.thread = threading.Thread(target=GamePad.start_loop, kwargs=dict(callback=callback), daemon=True)
        GamePad.thread.start()

    @staticmethod
    def stop_gamepad():
        if GamePad.thread is not None:
            GamePad.running = False
            GamePad.thread.join()
            GamePad.thread = None

