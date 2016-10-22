import java.util.Scanner;

public class Main {

	boolean isRunning = true;
	
	
	public Main(){
		init();
		gameLoop();
	}
	
	public static void main(String[] args) {
		new Main();
	}
	
	public void init(){
		
	}
	
	public void gameLoop(){
		while(isRunning){
			update();
		}
	}
	
	public void update(){
		
	}

}
