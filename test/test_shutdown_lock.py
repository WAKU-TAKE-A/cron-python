import sys
import unittest.mock
import threading

def test_request_shutdown_concurrency():
    from cron_python import main, EXIT_ERROR

    mock_scheduler = unittest.mock.MagicMock()
    mock_scheduler_class = unittest.mock.MagicMock(return_value=mock_scheduler)
    
    job_func = [None]
    
    def add_job_side_effect(func, *args, **kwargs):
        job_func[0] = func
        
    mock_scheduler.add_job.side_effect = add_job_side_effect
    mock_scheduler.running = True
    
    # We patch execute_job to return EXIT_ERROR which triggers request_shutdown
    with unittest.mock.patch("sys.argv", ["cron_python", "dummy.py", "--cron", "* * * * *", "--exit-on-script-error"]):
        with unittest.mock.patch("cron_python.BlockingScheduler", mock_scheduler_class):
            with unittest.mock.patch("cron_python.execute_job", return_value=EXIT_ERROR):
                with unittest.mock.patch("sys.exit"):
                    main()
                    
    assert job_func[0] is not None
    
    # Run the scheduled job from multiple threads concurrently
    # This will cause execute_job to return EXIT_ERROR and call request_shutdown multiple times
    threads = []
    for _ in range(20):
        t = threading.Thread(target=job_func[0])
        threads.append(t)
        
    for t in threads:
        t.start()
        
    for t in threads:
        t.join()
        
    # The lock in request_shutdown should ensure that scheduler.shutdown() is only called once
    assert mock_scheduler.shutdown.call_count == 1
